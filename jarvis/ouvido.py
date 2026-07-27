"""Reconhecimento de fala (STT) offline com faster-whisper, em português.

A captura usa um detector de silêncio simples baseado em energia (RMS): o
Jarvis começa a gravar quando você fala e para quando você cala. O modelo do
Whisper só roda no trecho gravado, em vez de ficar transcrevendo silêncio.
"""

from __future__ import annotations

import queue
import sys

import numpy as np

from . import configuracoes

# O Whisper espera áudio mono em 16 kHz, float32 normalizado entre -1 e 1.
TAXA = 16000
BLOCO = 1600  # 100 ms por bloco


class Ouvido:
    """Microfone + transcrição em português."""

    def __init__(self, tamanho_do_modelo: str | None = None):
        config = configuracoes.carregar()
        self.tamanho_do_modelo = tamanho_do_modelo or config["modelo_de_escuta"]
        self.limiar_de_silencio = config["limiar_de_silencio"]
        self.silencio_para_encerrar = config["silencio_para_encerrar"]
        self.duracao_maxima = config["duracao_maxima_da_fala"]

        from faster_whisper import WhisperModel

        # int8 em CPU: cabe na memória de qualquer máquina e é rápido o bastante
        # para conversa. O modelo é baixado na primeira execução e fica em cache.
        self.modelo = WhisperModel(
            self.tamanho_do_modelo,
            device="cpu",
            compute_type="int8",
            download_root=str(configuracoes.PASTA_MODELOS / "whisper"),
        )

    def transcrever(self, audio: np.ndarray) -> str:
        """Transcreve um trecho de áudio (float32, 16 kHz) para texto."""
        segmentos, _ = self.modelo.transcribe(
            audio,
            language="pt",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(segmento.text.strip() for segmento in segmentos).strip()

    def gravar_fala(self) -> np.ndarray | None:
        """Grava do microfone até detectar silêncio. None se ninguém falou."""
        import sounddevice as sd

        blocos: queue.Queue[np.ndarray] = queue.Queue()

        def capturar(dados, _quadros, _tempo, status):
            if status:
                print(f"[áudio] {status}", file=sys.stderr)
            blocos.put(dados[:, 0].copy())

        gravado: list[np.ndarray] = []
        falando = False
        blocos_em_silencio = 0
        blocos_para_encerrar = int(self.silencio_para_encerrar * TAXA / BLOCO)
        blocos_maximos = int(self.duracao_maxima * TAXA / BLOCO)

        with sd.InputStream(
            samplerate=TAXA, channels=1, dtype="float32", blocksize=BLOCO, callback=capturar
        ):
            while len(gravado) < blocos_maximos:
                bloco = blocos.get()
                energia = float(np.sqrt(np.mean(bloco**2)))

                if energia >= self.limiar_de_silencio:
                    falando = True
                    blocos_em_silencio = 0
                elif falando:
                    blocos_em_silencio += 1

                if falando:
                    gravado.append(bloco)
                    if blocos_em_silencio >= blocos_para_encerrar:
                        break

        if not gravado:
            return None
        return np.concatenate(gravado)

    def escutar(self) -> str:
        """Grava uma fala e devolve o texto transcrito ('' se não houve fala)."""
        audio = self.gravar_fala()
        if audio is None:
            return ""
        return self.transcrever(audio)
