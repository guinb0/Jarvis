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

# Os blocos chegam a cada 100 ms. Vários segundos sem nenhum significam que o
# dispositivo parou de entregar áudio — normalmente porque outro programa tomou
# o microfone em modo exclusivo (jogos costumam fazer isso ao abrir o chat de
# voz), ou porque ele foi desconectado.
ESPERA_MAXIMA_POR_BLOCO = 5.0

# Devolvido no lugar do áudio quando mandaram abandonar a gravação. Precisa ser
# distinto de None, que já significa "ninguém falou".
INTERROMPIDA = object()


class MicrofoneIndisponivel(OSError):
    """O microfone parou de entregar áudio no meio da captura.

    Existe porque o caso silencioso é o pior: sem isto, a espera pelo próximo
    bloco nunca termina e o Jarvis fica de pé, sem erro nenhum, simplesmente
    surdo para sempre.
    """


class Ouvido:
    """Microfone + transcrição em português."""

    def __init__(self, tamanho_do_modelo: str | None = None):
        config = configuracoes.carregar()
        self.tamanho_do_modelo = tamanho_do_modelo or config["modelo_de_escuta"]
        self.limiar_de_silencio = config["limiar_de_silencio"]
        self.silencio_para_encerrar = config["silencio_para_encerrar"]
        self.duracao_maxima = config["duracao_maxima_da_fala"]
        # beam 1 é bem mais rápido em CPU; 5 quase não melhora em fala curta.
        self.beam_size = int(config.get("whisper_beam_size", 1))

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
        import time

        inicio = time.perf_counter()
        # initial_prompt puxa o Whisper para o vocabulário dos comandos (e
        # corrige "Javis" → Jarvis com mais frequência).
        segmentos, _ = self.modelo.transcribe(
            audio,
            language="pt",
            beam_size=self.beam_size,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            condition_on_previous_text=False,
            without_timestamps=True,
            initial_prompt=(
                "Jarvis. Que horas são. Minhas tarefas. Status do GitHub. "
                "Relatório da semana. Já fiz. Pesquisar. Abrir. O que abriu."
            ),
        )
        texto = " ".join(segmento.text.strip() for segmento in segmentos).strip()
        print(
            f"[escuta] {self.tamanho_do_modelo} beam={self.beam_size} "
            f"{time.perf_counter() - inicio:.1f}s",
            file=sys.stderr,
        )
        return texto

    def gravar_fala(self, parar_se=None) -> np.ndarray | None:
        """Grava do microfone até detectar silêncio.

        `parar_se` é consultado a cada bloco de 100 ms; devolvendo True, a
        gravação é abandonada. É por aí que o gatilho de teclado consegue
        desligar a escuta sem esperar você falar.

        Devolve None se ninguém falou ou se a gravação foi abandonada.
        """
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
                if parar_se is not None and parar_se():
                    return INTERROMPIDA

                try:
                    bloco = blocos.get(timeout=ESPERA_MAXIMA_POR_BLOCO)
                except queue.Empty:
                    raise MicrofoneIndisponivel(
                        "o microfone parou de entregar áudio; outro programa "
                        "provavelmente o tomou em modo exclusivo"
                    ) from None

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

    def escutar(self, parar_se=None) -> str | None:
        """Grava uma fala e devolve o texto transcrito.

        `''` quando ninguém falou; `None` quando `parar_se` mandou abandonar.
        """
        audio = self.gravar_fala(parar_se)
        if audio is INTERROMPIDA:
            return None
        if audio is None:
            return ""
        return self.transcrever(audio)
