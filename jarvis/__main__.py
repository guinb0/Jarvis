"""Ponto de entrada do Jarvis.

    python -m jarvis                 # conversa por texto, respondendo em voz
    python -m jarvis --ouvir         # conversa por voz, de ponta a ponta
    python -m jarvis --mudo          # só texto, sem tocar áudio
    python -m jarvis --offline       # sem conversa aberta, só comandos locais
    python -m jarvis --dizer "oi"    # responde uma única frase e sai
    python -m jarvis --motor piper   # força a voz offline, sem internet
"""

from __future__ import annotations

import argparse
import sys
import time

from .cerebro import Cerebro
from .comandos import PedidoDeEncerramento
from .configuracoes import carregar

# Quantas falhas seguidas de captura são reclamadas no stderr antes de o Jarvis
# passar a tentar em silêncio. Ele nunca desiste de vez: sobe junto com o
# Windows para ficar de pé o dia inteiro, e um jogo pode segurar o microfone por
# horas — encerrar obrigaria a reiniciar tudo na mão depois de cada partida.
AVISOS_DE_AUDIO = 5

# Teto do intervalo entre tentativas, em segundos.
ESPERA_MAXIMA_DE_AUDIO = 15


def carregar_voz(mudo: bool, nome_da_voz: str | None, motor: str | None):
    """Devolve a voz carregada, ou None se estiver mudo / sem modelo baixado."""
    if mudo:
        return None

    try:
        from .voz import Voz

        voz = Voz(nome_da_voz, motor)
        if carregar()["usar_frases_gravadas"]:
            quantas = voz.carregar_frases_gravadas()
            if quantas:
                print(f"[voz] {quantas} frases fixas na voz do JARVIS.")
        return voz
    except FileNotFoundError as erro:
        print(f"[voz desativada] {erro}\n", file=sys.stderr)
    except ImportError:
        print(
            "[voz desativada] dependências ausentes. Rode: pip install -r requirements.txt\n",
            file=sys.stderr,
        )
    return None


def carregar_ouvido():
    """Devolve o ouvido carregado, ou None se as dependências faltarem."""
    try:
        from .ouvido import Ouvido

        print("Carregando o modelo de escuta (a primeira vez baixa o modelo)...")
        return Ouvido()
    except ImportError:
        print(
            "[escuta indisponível] falta o faster-whisper. "
            "Rode: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return None


def responder(cerebro: Cerebro, voz, frase: str) -> None:
    if voz is None:
        print(f"Jarvis: {cerebro.responder(frase)}")
        return

    # Fala cada frase assim que ela fica pronta, sem esperar a resposta
    # inteira. O gerador é consumido pela thread de síntese lá dentro.
    def partes():
        for parte in cerebro.responder_em_partes(frase):
            print(f"Jarvis: {parte}")
            yield parte

    voz.falar_em_fluxo(partes())


def anunciar(config: dict, voz, texto: str) -> None:
    print(f"Jarvis: {texto}")
    if voz:
        voz.falar(texto)


def anunciar_estado(config: dict, voz, ativando: bool) -> None:
    """Confirma que o assistente acordou, ou que voltou a dormir."""
    if not config["avisar_ativacao"]:
        return

    texto = config["aviso_ao_ativar"] if ativando else config["aviso_ao_desativar"]
    print(f"Jarvis: {texto}")

    if voz:
        voz.falar(texto)
    else:
        from .gatilho import Gatilho

        Gatilho.bipar(ativando)


def laco_de_texto(cerebro: Cerebro, voz) -> int:
    modo = "com conversa aberta" if cerebro.conversa else "só comandos locais"
    print(f"({modo} — digite 'ajuda' para ver os comandos, 'sair' para encerrar)\n")

    while True:
        try:
            frase = input("Você: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        try:
            responder(cerebro, voz, frase)
        except PedidoDeEncerramento as despedida:
            anunciar(cerebro.config, voz, str(despedida))
            return 0


def laco_de_voz(cerebro: Cerebro, voz, ouvido, gatilho=None) -> int:
    exige_ativacao = cerebro.config["exigir_palavra_de_ativacao"]
    if gatilho:
        dica = f"aperte {gatilho.descricao} para falar comigo"
    elif exige_ativacao:
        dica = f"diga '{cerebro.config['palavra_de_ativacao']}' antes do pedido"
    else:
        dica = "é só falar"

    modo = "com conversa aberta" if cerebro.conversa else "só comandos locais"
    print(f"({dica} — {modo}; Ctrl+C para encerrar)\n")

    # No login o microfone às vezes ainda não subiu, e outro programa pode tomá-lo
    # em modo exclusivo. Nesses casos insistimos: morrer calado seria pior, ainda
    # mais quando o Jarvis inicia sozinho com o Windows.
    falhas_seguidas = 0
    estado = {"acordado": gatilho is None}  # sem gatilho, já nasce escutando

    from .cobrador import Cobrador

    cobrador = Cobrador(
        cerebro.config,
        voz,
        esta_acordado=lambda: estado["acordado"],
    )
    cobrador.iniciar()

    try:
        while True:
            try:
                if gatilho and not estado["acordado"]:
                    # Dormindo: o microfone nem é aberto até você chamar.
                    print(f"· dormindo — {gatilho.descricao}   ", end="\r", flush=True)
                    gatilho.esperar()
                    anunciar_estado(cerebro.config, voz, ativando=True)
                    estado["acordado"] = True

                print("· escutando...        ", end="\r", flush=True)
                # O gatilho também desliga: consultado a cada 100 ms durante a
                # gravação, para não ser preciso falar algo só para poder desligar.
                frase = ouvido.escutar(parar_se=gatilho.disparou if gatilho else None)

                if frase is None:  # apertaram a tecla de novo
                    anunciar_estado(cerebro.config, voz, ativando=False)
                    estado["acordado"] = False
                    continue

                if falhas_seguidas:
                    print("[áudio] microfone de volta.", file=sys.stderr)
                falhas_seguidas = 0
            except KeyboardInterrupt:
                print("\n")
                return 0
            except Exception as erro:
                falhas_seguidas += 1
                espera = min(2 * falhas_seguidas, ESPERA_MAXIMA_DE_AUDIO)

                if falhas_seguidas <= AVISOS_DE_AUDIO:
                    print(
                        f"\n[áudio] microfone indisponível ({erro}). "
                        f"Nova tentativa em {espera}s.",
                        file=sys.stderr,
                    )
                    if falhas_seguidas == AVISOS_DE_AUDIO:
                        print(
                            "[áudio] a partir daqui sigo tentando em silêncio, "
                            "até o microfone voltar.",
                            file=sys.stderr,
                        )

                time.sleep(espera)
                continue

            try:
                if frase:
                    print(f"Você: {frase}")
                    pedido = cerebro.extrair_pedido(frase)
                    if pedido is not None:  # None = falaram, mas não com o Jarvis
                        responder(cerebro, voz, pedido)
            except PedidoDeEncerramento as despedida:
                anunciar(cerebro.config, voz, str(despedida))
                return 0

            # Continua acordado de propósito: só volta a dormir quando você apertar
            # a tecla de novo, tratada logo acima.
    finally:
        cobrador.parar()


def main() -> int:
    analisador = argparse.ArgumentParser(prog="jarvis", description="Assistente pessoal.")
    analisador.add_argument("--ouvir", action="store_true", help="conversar por voz")
    analisador.add_argument("--mudo", action="store_true", help="não reproduzir áudio")
    analisador.add_argument("--dizer", metavar="FRASE", help="responder uma frase e sair")
    analisador.add_argument("--voz", metavar="NOME", help="usar outra voz")
    analisador.add_argument(
        "--motor",
        choices=("edge", "piper"),
        help="edge: neural e natural, pela internet; piper: offline, mais robótico",
    )
    analisador.add_argument(
        "--sempre-escutando",
        action="store_true",
        help="ignorar o gatilho de teclado e responder a tudo que ouvir",
    )
    analisador.add_argument(
        "--offline", action="store_true", help="não consultar o Claude para conversa aberta"
    )
    argumentos = analisador.parse_args()

    config = carregar()
    cerebro = Cerebro(usar_nuvem=not argumentos.offline)
    voz = carregar_voz(argumentos.mudo, argumentos.voz, argumentos.motor)

    if argumentos.dizer:
        try:
            responder(cerebro, voz, argumentos.dizer)
        except PedidoDeEncerramento as despedida:
            print(f"Jarvis: {despedida}")
        return 0

    ouvido = carregar_ouvido() if argumentos.ouvir else None
    if argumentos.ouvir and ouvido is None:
        return 1

    gatilho = None
    if ouvido and not argumentos.sempre_escutando:
        from .gatilho import carregar_gatilho

        gatilho = carregar_gatilho(config)

        # Sintetiza os avisos agora: assim a confirmação sai no instante do
        # atalho, em vez de esperar a Edge responder a cada ativação.
        if gatilho and voz and config["avisar_ativacao"]:
            voz.preparar(config["aviso_ao_ativar"], config["aviso_ao_desativar"])

    if config["falar_ao_iniciar"]:
        anunciar(config, voz, f"Sistemas online, {config['tratamento']}.")

    if ouvido:
        try:
            return laco_de_voz(cerebro, voz, ouvido, gatilho)
        finally:
            if gatilho:
                gatilho.parar()

    # Modo texto: cobrança periódica também (se TickTick estiver ligado).
    from .cobrador import Cobrador

    cobrador = Cobrador(cerebro.config, voz)
    cobrador.iniciar()
    try:
        return laco_de_texto(cerebro, voz)
    finally:
        cobrador.parar()


if __name__ == "__main__":
    raise SystemExit(main())
