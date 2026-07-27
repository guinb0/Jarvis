"""Baixa um modelo de voz Piper para a pasta `modelos/`.

    python scripts/baixar_voz.py                      # baixa a voz padrão
    python scripts/baixar_voz.py pt_PT-tugão-medium   # baixa outra voz

Vozes em português disponíveis no repositório rhasspy/piper-voices:

    pt_BR-faber-medium     masculina, brasileira  (padrão)
    pt_BR-edresson-low     masculina, brasileira, mais leve
    pt_PT-tugão-medium     masculina, de Portugal
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from jarvis.configuracoes import PASTA_MODELOS, VOZ_PADRAO  # noqa: E402

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def url_do_modelo(nome_da_voz: str, extensao: str) -> str:
    """Monta a URL a partir do nome da voz (ex.: pt_BR-faber-medium)."""
    try:
        idioma, locutor, qualidade = nome_da_voz.split("-")
    except ValueError:
        raise SystemExit(
            f"Nome de voz inválido: '{nome_da_voz}'. "
            "Use o formato idioma-locutor-qualidade, ex.: pt_BR-faber-medium"
        )

    familia = idioma.split("_")[0]
    caminho = f"{familia}/{idioma}/{locutor}/{qualidade}/{nome_da_voz}{extensao}"
    return f"{BASE}/{quote(caminho)}?download=true"


def baixar(url: str, destino: Path) -> None:
    if destino.exists():
        print(f"  já existe: {destino.name}")
        return

    resposta = requests.get(url, stream=True, timeout=60)
    if resposta.status_code == 404:
        raise SystemExit(f"Voz não encontrada no repositório:\n  {url}")
    resposta.raise_for_status()

    total = int(resposta.headers.get("content-length", 0))
    baixado = 0
    parcial = destino.parent / (destino.name + ".parcial")

    with parcial.open("wb") as arquivo:
        for bloco in resposta.iter_content(chunk_size=1 << 16):
            arquivo.write(bloco)
            baixado += len(bloco)
            if total:
                print(f"\r  {destino.name}: {baixado * 100 // total}%", end="", flush=True)

    parcial.replace(destino)
    print(f"\r  {destino.name}: pronto ({baixado / 1e6:.1f} MB)")


def main() -> int:
    nome_da_voz = sys.argv[1] if len(sys.argv) > 1 else VOZ_PADRAO
    PASTA_MODELOS.mkdir(parents=True, exist_ok=True)

    print(f"Baixando a voz '{nome_da_voz}' para {PASTA_MODELOS}")
    for extensao in (".onnx", ".onnx.json"):
        baixar(url_do_modelo(nome_da_voz, extensao), PASTA_MODELOS / f"{nome_da_voz}{extensao}")

    print("\nTeste com:  python -m jarvis --dizer \"bom dia\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
