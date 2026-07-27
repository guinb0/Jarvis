"""Síntese de voz (TTS) offline com Piper, em português.

O Piper mudou a assinatura de `synthesize` entre versões, então a classe abaixo
normaliza as duas formas conhecidas e sempre devolve PCM int16 cru.
"""

from __future__ import annotations

import wave
from pathlib import Path

from . import configuracoes


class Voz:
    """Envelope em torno de uma voz Piper carregada na memória."""

    def __init__(self, nome_da_voz: str | None = None):
        config = configuracoes.carregar()
        self.nome = nome_da_voz or config["voz"]
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
        """Converte texto em PCM int16 mono cru."""
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

    def falar(self, texto: str) -> None:
        """Sintetiza e toca o texto nos alto-falantes."""
        import numpy as np
        import sounddevice as sd

        audio = np.frombuffer(self.sintetizar(texto), dtype=np.int16)
        sd.play(audio, self.taxa_de_amostragem)
        sd.wait()

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
