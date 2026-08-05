"""Grava as frases fixas do Jarvis com a voz clonada do JARVIS (XTTS-v2).

Rode de novo sempre que instalar um jogo novo ou criar um comando — as frases
são lidas do próprio código, então a lista se atualiza sozinha.

    C:\\Users\\Guilh\\Documents\\Jarvis\\venv-clone\\Scripts\\python.exe ^
        scripts\\gerar_frases_jarvis.py

POR QUE UM AMBIENTE SEPARADO
    A clonagem precisa de PyTorch e coqui-tts, que exigem versões de numpy e
    transformers incompatíveis com a escuta do Jarvis. Instalar junto quebraria
    o assistente, então vive em `venv-clone`, fora do projeto.

POR QUE ISTO É UM ARQUIVO GRAVADO, E NÃO SÍNTESE AO VIVO
    Sem CUDA o XTTS roda na CPU a ~3,9x o tempo real: uma frase de 5s leva 20s
    para sair. Inviável em conversa. Gravando de uma vez, o Jarvis só toca o
    arquivo depois — instantâneo.

MONTAGEM DO AMBIENTE (uma vez)
    python -m venv C:\\Users\\Guilh\\Documents\\Jarvis\\venv-clone
    venv-clone\\Scripts\\pip install coqui-tts torch torchaudio torchcodec
    venv-clone\\Scripts\\pip install "transformers>=4.57,<5"
    E o FFmpeg 7 (o 8 não serve) em Documents\\Jarvis\\ffmpeg.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ["COQUI_TOS_AGREED"] = "1"

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# O torchcodec (leitura de áudio no PyTorch 2.9+) exige as bibliotecas do
# FFmpeg 4 a 7 no PATH. A versão 8 é recusada.
FFMPEG = RAIZ.parent / "ffmpeg" / "ffmpeg-n7.1-latest-win64-gpl-shared-7.1" / "bin"
if FFMPEG.is_dir():
    os.environ["PATH"] = f"{FFMPEG}{os.pathsep}{os.environ['PATH']}"

# Trecho de referência: 25s do JARVIS, sem música, várias entonações.
REFERENCIA = RAIZ / "amostras-de-voz" / "REFERENCIA - Jarvis (limpa).wav"
DESTINO = RAIZ / "frases-jarvis"


def montar_frases(tratamento: str) -> dict[str, str]:
    """Texto -> nome do arquivo, lendo as frases do próprio código do Jarvis."""
    frases: dict[str, str] = {}

    def add(chave: str, texto: str) -> None:
        frases[texto] = chave

    add("ativado", "Sistema ativado.")
    add("desativado", "Sistema desativado.")
    add("online", f"Sistemas online, {tratamento}.")

    for i, periodo in enumerate(["Bom dia", "Boa tarde", "Boa noite"]):
        add(f"saudacao_{i}", f"{periodo}, {tratamento}. Em que posso ajudar?")

    add("ate_logo", f"Até logo, {tratamento}.")
    add("volume_mais", "Volume aumentado.")
    add("volume_menos", "Volume reduzido.")
    add("volume_mudo", "Som cortado.")
    add("bloqueando", f"Bloqueando, {tratamento}.")
    add("pois_nao", f"Pois não, {tratamento}?")
    add(
        "nao_sei",
        f"Ainda não sei fazer isso, {tratamento}. Diga 'ajuda' para ver o que eu entendo.",
    )

    add("sem_credencial", "Não estou conectado à nuvem: falta configurar a credencial da Anthropic.")
    add("limite", "Estou recebendo pedidos demais. Tente de novo em instantes.")
    add("sem_internet", "Não consegui acessar a internet agora.")
    add("erro_nuvem", "Deu problema ao consultar a nuvem.")
    add("recusa", "Prefiro não responder isso.")
    add("sem_resposta", "Não consegui formular uma resposta.")

    from jarvis.comandos.jogos import catalogo

    for i, (nome, _uri) in enumerate(sorted(catalogo().values())):
        add(f"jogo_{i}", f"Abrindo {nome}, {tratamento}.")

    from jarvis.comandos.sistema import PROGRAMAS

    for i, apelido in enumerate(sorted(PROGRAMAS)):
        add(f"programa_{i}", f"Abrindo {apelido}, {tratamento}.")

    return frases


def main() -> int:
    from jarvis.configuracoes import carregar

    if not REFERENCIA.exists():
        print(f"Falta o trecho de referência: {REFERENCIA}", file=sys.stderr)
        return 1

    frases = montar_frases(carregar()["tratamento"])
    DESTINO.mkdir(parents=True, exist_ok=True)
    print(f"{len(frases)} frases a gravar.\n")

    print("Carregando o XTTS-v2...")
    inicio = time.monotonic()
    from TTS.api import TTS

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False)
    print(f"pronto em {time.monotonic() - inicio:.0f}s\n")

    indice: dict[str, str] = {}
    inicio = time.monotonic()
    for n, (texto, chave) in enumerate(frases.items(), 1):
        arquivo = f"{chave}.wav"
        marca = time.monotonic()
        tts.tts_to_file(
            text=texto,
            speaker_wav=str(REFERENCIA),
            language="pt",
            file_path=str(DESTINO / arquivo),
        )
        indice[texto] = arquivo
        print(f"  [{n:2}/{len(frases)}] {time.monotonic() - marca:5.1f}s  {texto[:56]}")

    (DESTINO / "indice.json").write_text(
        json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nTotal: {(time.monotonic() - inicio) / 60:.1f} min")
    print(f"Gravado em: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
