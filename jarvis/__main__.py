"""Ponto de entrada do Jarvis.

    python -m jarvis                 # conversa por texto, respondendo em voz
    python -m jarvis --ouvir         # conversa por voz, de ponta a ponta
    python -m jarvis --mudo          # só texto, sem tocar áudio
    python -m jarvis --offline       # sem conversa aberta, só comandos locais
    python -m jarvis --dizer "oi"    # responde uma única frase e sai
"""

from __future__ import annotations

import argparse
import sys

from .cerebro import Cerebro
from .comandos import PedidoDeEncerramento
from .configuracoes import carregar


def carregar_voz(mudo: bool, nome_da_voz: str | None):
    """Devolve a voz carregada, ou None se estiver mudo / sem modelo baixado."""
    if mudo:
        return None

    try:
        from .voz import Voz

        return Voz(nome_da_voz)
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
    resposta = cerebro.responder(frase)
    print(f"Jarvis: {resposta}")
    if voz:
        voz.falar(resposta)


def anunciar(config: dict, voz, texto: str) -> None:
    print(f"Jarvis: {texto}")
    if voz:
        voz.falar(texto)


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


def laco_de_voz(cerebro: Cerebro, voz, ouvido) -> int:
    exige_ativacao = cerebro.config["exigir_palavra_de_ativacao"]
    dica = (
        f"diga '{cerebro.config['palavra_de_ativacao']}' antes do pedido"
        if exige_ativacao
        else "é só falar"
    )
    print(f"(escutando — {dica}; Ctrl+C para encerrar)\n")

    while True:
        try:
            print("· escutando...", end="\r", flush=True)
            frase = ouvido.escutar()
        except KeyboardInterrupt:
            print("\n")
            return 0

        if not frase:
            continue

        print(f"Você: {frase}")
        pedido = cerebro.extrair_pedido(frase)
        if pedido is None:
            continue  # falaram, mas não com o Jarvis

        try:
            responder(cerebro, voz, pedido)
        except PedidoDeEncerramento as despedida:
            anunciar(cerebro.config, voz, str(despedida))
            return 0


def main() -> int:
    analisador = argparse.ArgumentParser(prog="jarvis", description="Assistente pessoal.")
    analisador.add_argument("--ouvir", action="store_true", help="conversar por voz")
    analisador.add_argument("--mudo", action="store_true", help="não reproduzir áudio")
    analisador.add_argument("--dizer", metavar="FRASE", help="responder uma frase e sair")
    analisador.add_argument("--voz", metavar="NOME", help="usar outra voz do Piper")
    analisador.add_argument(
        "--offline", action="store_true", help="não consultar o Claude para conversa aberta"
    )
    argumentos = analisador.parse_args()

    config = carregar()
    cerebro = Cerebro(usar_nuvem=not argumentos.offline)
    voz = carregar_voz(argumentos.mudo, argumentos.voz)

    if argumentos.dizer:
        try:
            responder(cerebro, voz, argumentos.dizer)
        except PedidoDeEncerramento as despedida:
            print(f"Jarvis: {despedida}")
        return 0

    ouvido = carregar_ouvido() if argumentos.ouvir else None
    if argumentos.ouvir and ouvido is None:
        return 1

    if config["falar_ao_iniciar"]:
        anunciar(config, voz, f"Sistemas online, {config['tratamento']}.")

    if ouvido:
        return laco_de_voz(cerebro, voz, ouvido)
    return laco_de_texto(cerebro, voz)


if __name__ == "__main__":
    raise SystemExit(main())
