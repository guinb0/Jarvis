"""Síntese de voz (TTS) em português, com dois motores.

`edge` usa as vozes neurais da Microsoft: soam naturais e não pesam na máquina,
mas o texto da resposta viaja pela internet. `piper` roda inteiro aqui dentro,
sem rede, ao custo de um timbre bem mais robótico.

O padrão é `edge` com o Piper de reserva: se a rede cair no meio de uma frase, a
próxima já sai pelo Piper, sem derrubar o assistente. Falha de síntese nunca
interrompe a conversa — no pior caso o Jarvis responde só por texto.
"""

from __future__ import annotations

import io
import re
import sys
import threading
import wave
from pathlib import Path

from . import configuracoes

_TRAVA_DE_FALA = threading.Lock()


def para_fala(texto: str) -> str:
    """Limpa o texto para a TTS não ler pontuação e símbolos em voz alta.

    Edge e Piper costumam falar hífen, travessão, dois-pontos, barra e
    marcadores de lista como palavras. O modelo e alguns comandos locais
    ainda escrevem assim — daí a limpeza antes de sintetizar.
    """
    if not texto:
        return texto

    t = texto.replace("\r\n", "\n").replace("\r", "\n")
    # Markdown e ênfase.
    t = re.sub(r"[*_`#]+", " ", t)
    # URLs: não soletrar barra e ponto.
    t = re.sub(r"https?://\S+", " um link ", t)
    t = re.sub(r"\bwww\.\S+", " um site ", t)
    # Travessão / hífen usados como pausa entre orações.
    t = re.sub(r"\s*[—–−]+\s*", ", ", t)
    t = re.sub(r"\s+-\s+", ", ", t)
    # Listas: "- item" ou "1. item" no começo da linha.
    t = re.sub(r"(?m)^\s*[-•·]\s*", "", t)
    t = re.sub(r"(?m)^\s*\d+[.)]\s*", "", t)
    # Símbolos que a TTS soletra.
    t = t.replace("/", " ")
    t = t.replace("\\", " ")
    t = t.replace("|", " ")
    t = t.replace("@", " ")
    t = t.replace("&", " e ")
    t = t.replace("=", " ")
    t = t.replace("+", " mais ")
    t = t.replace("%", " por cento")
    # Dois-pontos e ponto-e-vírgula viram pausa, não "dois pontos".
    t = t.replace(":", ",")
    t = t.replace(";", ",")
    # Parênteses / colchetes: some o símbolo, mantém o conteúdo.
    t = re.sub(r"[\[\]\(\)\{\}<>]", " ", t)
    # Aspas soltas.
    t = t.replace('"', " ").replace("'", " ").replace("“", " ").replace("”", " ")
    t = t.replace("‘", " ").replace("’", " ")
    # Quebras de linha viram pausa.
    t = t.replace("\n", ". ")
    # Várias pontuações / espaços sobrando.
    t = re.sub(r"[!]{2,}", "!", t)
    t = re.sub(r"[?]{2,}", "?", t)
    t = re.sub(r"[.]{2,}", ".", t)
    t = re.sub(r",\s*,+", ",", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.!?])", r"\1", t)
    return t.strip(" ,")


# Corta em ponto final, interrogação ou exclamação seguidos de espaço e
# maiúscula. Exige 25 caracteres antes do corte para não picar "R$ 5,11" nem
# abreviações como "Dr." em frases separadas.
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ])")
_MINIMO_POR_FRASE = 25


def _partir_em_frases(texto: str) -> list[str]:
    """Divide a resposta em frases, para sintetizar uma enquanto toca a outra."""
    partes: list[str] = []
    for pedaco in _FIM_DE_FRASE.split(texto.strip()):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        # Junta o que ficou curto demais: uma frase de três palavras não paga
        # o custo de uma ida à rede só para ela.
        if partes and len(partes[-1]) < _MINIMO_POR_FRASE:
            partes[-1] = f"{partes[-1]} {pedaco}"
        else:
            partes.append(pedaco)
    return partes or [texto.strip()]


def _tocar(pcm: bytes, taxa: int) -> None:
    """Reproduz PCM int16 mono nos alto-falantes e espera terminar."""
    import numpy as np
    import sounddevice as sd

    sd.play(np.frombuffer(pcm, dtype=np.int16), taxa)
    sd.wait()


class _VozBase:
    """Parte comum aos motores: tocar e gravar PCM int16 mono."""

    nome: str
    taxa_de_amostragem: int

    def sintetizar(self, texto: str) -> bytes:
        """Converte texto em PCM int16 mono cru."""
        raise NotImplementedError

    def falar(self, texto: str) -> None:
        """Sintetiza e toca o texto nos alto-falantes."""
        _tocar(self.sintetizar(texto), self.taxa_de_amostragem)

    def salvar(self, texto: str, destino: str | Path) -> Path:
        """Sintetiza o texto e grava em um arquivo .wav."""
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(destino), "wb") as arquivo:
            arquivo.setnchannels(1)
            arquivo.setsampwidth(2)  # int16
            arquivo.setframerate(self.taxa_de_amostragem)
            arquivo.writeframes(self.sintetizar(texto))

        return destino


class VozEdge(_VozBase):
    """Voz neural do Edge TTS. Precisa de internet; não precisa de modelo baixado."""

    def __init__(self, nome_da_voz: str | None = None):
        config = configuracoes.carregar()
        self.nome = nome_da_voz or config["voz_edge"]

        import edge_tts  # noqa: F401  — falha cedo se a dependência faltar

        # A Edge devolve MP3 a 24 kHz; a taxa real é confirmada na decodificação.
        self.taxa_de_amostragem = 24000

    def sintetizar(self, texto: str) -> bytes:
        import edge_tts
        import soundfile as sf

        comunicacao = edge_tts.Communicate(para_fala(texto), self.nome)
        mp3 = b"".join(
            pedaco["data"] for pedaco in comunicacao.stream_sync() if pedaco["type"] == "audio"
        )

        if not mp3:
            raise RuntimeError(f"a Edge não devolveu áudio para a voz '{self.nome}'")

        audio, taxa = sf.read(io.BytesIO(mp3), dtype="int16")
        self.taxa_de_amostragem = taxa
        return audio.tobytes()


class VozPiper(_VozBase):
    """Voz do Piper, carregada na memória a partir de um .onnx local.

    O Piper mudou a assinatura de `synthesize` entre versões, então as duas
    formas conhecidas são normalizadas aqui.
    """

    def __init__(self, nome_da_voz: str | None = None):
        config = configuracoes.carregar()
        self.nome = nome_da_voz or config["voz_piper"]
        self.caminho = configuracoes.caminho_do_modelo(self.nome)

        if not self.caminho.exists():
            raise FileNotFoundError(
                f"Modelo de voz '{self.nome}' não encontrado em {self.caminho}.\n"
                f"Baixe com:  python scripts/baixar_voz.py {self.nome}"
            )

        from piper import PiperVoice  # importado aqui para o erro acima vir antes

        self._voz = PiperVoice.load(str(self.caminho))
        self.taxa_de_amostragem = self._voz.config.sample_rate

    def sintetizar(self, texto: str) -> bytes:
        texto = para_fala(texto)
        pedacos: list[bytes] = []

        # Piper >= 1.3: synthesize() devolve objetos AudioChunk.
        # Piper 1.2: usa synthesize_stream_raw(), que já devolve bytes.
        if hasattr(self._voz, "synthesize"):
            for pedaco in self._voz.synthesize(texto):
                pedacos.append(
                    pedaco.audio_int16_bytes if hasattr(pedaco, "audio_int16_bytes") else pedaco
                )
        else:
            pedacos.extend(self._voz.synthesize_stream_raw(texto))

        return b"".join(pedacos)


class Voz:
    """Motor escolhido, com o Piper de reserva quando o principal é a Edge.

    Delega tudo ao motor ativo. Se a Edge falhar (rede fora, serviço instável),
    troca para o Piper de uma vez e avisa uma única vez no stderr.
    """

    def __init__(self, nome_da_voz: str | None = None, motor: str | None = None):
        config = configuracoes.carregar()
        self.motor = motor or config["motor"]

        self._ja_avisou = False
        # Frases fixas ("Sistema ativado") sintetizadas uma vez e guardadas
        # prontas: a confirmação sai na hora, sem a espera da rede.
        self._prontas: dict[str, tuple[bytes, int]] = {}

        if self.motor == "piper":
            self._ativo: _VozBase = VozPiper(nome_da_voz)
            self._reserva_disponivel = False
        else:
            self._ativo = VozEdge(nome_da_voz)
            # Só vale tentar a reserva se o modelo do Piper já estiver baixado.
            self._reserva_disponivel = configuracoes.caminho_do_modelo(
                config["voz_piper"]
            ).exists()

    @property
    def nome(self) -> str:
        return self._ativo.nome

    @property
    def taxa_de_amostragem(self) -> int:
        return self._ativo.taxa_de_amostragem

    def _avisar(self, mensagem: str) -> None:
        """Escreve no stderr só na primeira falha, para não poluir a conversa."""
        if not self._ja_avisou:
            print(f"[voz] {mensagem}", file=sys.stderr)
            self._ja_avisou = True

    def _trocar_para_reserva(self, erro: Exception) -> bool:
        """Troca para o Piper. Devolve False se não houver reserva utilizável.

        Sem o modelo baixado seguimos na Edge de propósito: a rede pode voltar,
        e aí as próximas frases voltam a sair faladas sozinhas.
        """
        if not self._reserva_disponivel:
            self._avisar(
                f"falha na Edge ({erro}). Sem o modelo do Piper baixado, sigo só por "
                "texto até a rede voltar. Baixe a reserva com: python scripts/baixar_voz.py"
            )
            return False

        self._avisar(f"falha na Edge ({erro}). Passando para o Piper offline.")
        self._ativo = VozPiper()
        self.motor = "piper"
        self._reserva_disponivel = False
        return True

    def carregar_frases_gravadas(self, pasta: Path | None = None) -> int:
        """Carrega frases já gravadas em disco (a voz clonada do JARVIS).

        São as respostas fixas do assistente, sintetizadas de uma vez pelo
        `scripts/gerar_frases_jarvis.py`. Tudo que não estiver aqui — as
        respostas do Claude, que mudam sempre — continua saindo pela Edge.
        """
        import json

        pasta = pasta or configuracoes.PASTA_FRASES
        indice = pasta / "indice.json"
        if not indice.exists():
            return 0

        try:
            import soundfile as sf

            mapa = json.loads(indice.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            self._avisar(f"não consegui ler as frases gravadas: {erro}")
            return 0

        carregadas = 0
        for texto, arquivo in mapa.items():
            caminho = pasta / arquivo
            if not caminho.exists():
                continue
            try:
                dados, taxa = sf.read(caminho, dtype="int16")
                self._prontas[texto] = (dados.tobytes(), taxa)
                carregadas += 1
            except Exception as erro:
                self._avisar(f"frase gravada '{arquivo}' ilegível ({erro}).")

        return carregadas

    def preparar(self, *textos: str) -> None:
        """Sintetiza frases fixas de antemão, para tocarem sem espera depois.

        Falhar aqui não é problema: a frase simplesmente será sintetizada na
        hora, como qualquer outra.
        """
        for texto in textos:
            if not texto or texto in self._prontas:
                continue
            try:
                self._prontas[texto] = (
                    self._ativo.sintetizar(texto),
                    self._ativo.taxa_de_amostragem,
                )
            except Exception as erro:
                self._avisar(f"não consegui preparar '{texto}' ({erro}).")
                return

    def falar(self, texto: str) -> None:
        with _TRAVA_DE_FALA:
            self._falar_sem_trava(texto)

    def _falar_sem_trava(self, texto: str) -> None:
        # Frases gravadas batem no texto original; a limpeza só entra na síntese.
        pronta = self._prontas.get(texto) or self._prontas.get(para_fala(texto))
        if pronta is not None:
            try:
                _tocar(*pronta)
                return
            except Exception as erro:
                self._avisar(f"não consegui tocar o aviso: {erro}")
                return

        limpo = para_fala(texto)
        try:
            self._falar_em_cadeia(limpo)
        except Exception as erro:  # rede, serviço fora, dispositivo de áudio
            if self.motor == "piper":
                self._avisar(f"não consegui falar: {erro}")
                return
            if self._trocar_para_reserva(erro):
                try:
                    self._ativo.falar(limpo)
                except Exception as erro_reserva:
                    print(f"[voz] o Piper também falhou: {erro_reserva}", file=sys.stderr)

    def falar_em_fluxo(self, partes) -> None:
        """Fala um fluxo de frases que ainda está sendo produzido.

        Recebe um iterável que vai entregando frases conforme o Claude as
        escreve. A síntese corre numa thread à frente da reprodução, então a
        primeira frase começa a tocar enquanto a segunda ainda está chegando
        pela rede — e a espera vira a da primeira frase, não a da resposta toda.
        """
        import queue
        import threading

        with _TRAVA_DE_FALA:
            fila: queue.Queue = queue.Queue(maxsize=2)
            FIM = object()

            def sintetizar_adiante() -> None:
                try:
                    for parte in partes:
                        if not parte or not parte.strip():
                            continue
                        pronta = self._prontas.get(parte) or self._prontas.get(
                            para_fala(parte)
                        )
                        if pronta is not None:
                            fila.put(pronta)
                        else:
                            fila.put(
                                (
                                    self._ativo.sintetizar(para_fala(parte)),
                                    self._ativo.taxa_de_amostragem,
                                )
                            )
                except BaseException as erro:  # noqa: BLE001 — repassado abaixo
                    fila.put(erro)
                    return
                fila.put(FIM)

            threading.Thread(target=sintetizar_adiante, daemon=True).start()

            while True:
                item = fila.get()
                if item is FIM:
                    return
                if isinstance(item, BaseException):
                    # Inclui o PedidoDeEncerramento vindo de um comando: precisa
                    # chegar inteiro à thread principal para o laço encerrar.
                    raise item
                try:
                    _tocar(*item)
                except Exception as erro:
                    self._avisar(f"não consegui tocar: {erro}")
                    return

    def _falar_em_cadeia(self, texto: str) -> None:
        """Toca a primeira frase enquanto sintetiza as seguintes.

        Numa resposta de três frases isso derruba a espera pelo primeiro som de
        toda a síntese para só a da primeira frase — o resto acontece enquanto
        você já está ouvindo.
        """
        import queue
        import threading

        frases = _partir_em_frases(texto)
        if len(frases) < 2:
            self._ativo.falar(texto)
            return

        # Limite de 2 na fila: adianta o trabalho sem sintetizar a resposta
        # inteira à toa se a fala for interrompida.
        fila: queue.Queue = queue.Queue(maxsize=2)
        FIM = object()

        def sintetizar_adiante() -> None:
            for frase in frases:
                try:
                    fila.put((self._ativo.sintetizar(frase), self._ativo.taxa_de_amostragem))
                except Exception as erro:  # noqa: BLE001 — repassado à thread principal
                    fila.put(erro)
                    return
            fila.put(FIM)

        threading.Thread(target=sintetizar_adiante, daemon=True).start()

        while True:
            item = fila.get()
            if item is FIM:
                return
            if isinstance(item, Exception):
                raise item
            _tocar(*item)

    def sintetizar(self, texto: str) -> bytes:
        return self._ativo.sintetizar(para_fala(texto))

    def salvar(self, texto: str, destino: str | Path) -> Path:
        return self._ativo.salvar(para_fala(texto), destino)
