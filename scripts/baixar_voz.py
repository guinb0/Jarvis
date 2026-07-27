"""Baixa modelos de voz do Piper para a pasta `modelos/`.

    python scripts/baixar_voz.py                      # baixa a voz padrão
    python scripts/baixar_voz.py pt_BR-jeff-medium    # baixa outra voz
    python scripts/baixar_voz.py --listar             # mostra as vozes em português

Usa o downloader oficial do Piper, que resolve a URL a partir do catálogo
`voices.json` — assim novas vozes passam a funcionar sem mexer neste script.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from jarvis.configuracoes import PASTA_MODELOS, VOZES_EM_PORTUGUES, VOZ_PADRAO  # noqa: E402


def listar() -> int:
    print("Vozes em português disponíveis:\n")
    largura = max(len(nome) for nome in VOZES_EM_PORTUGUES)
    for nome, descricao in VOZES_EM_PORTUGUES.items():
        padrao = "  (padrão)" if nome == VOZ_PADRAO else ""
        print(f"  {nome.ljust(largura)}  {descricao}{padrao}")
    print(f"\nBaixe com:  python scripts/baixar_voz.py {VOZ_PADRAO}")
    return 0


def main() -> int:
    argumentos = sys.argv[1:]
    if "--listar" in argumentos or "-l" in argumentos:
        return listar()

    from piper.download_voices import download_voice

    nome_da_voz = argumentos[0] if argumentos else VOZ_PADRAO
    PASTA_MODELOS.mkdir(parents=True, exist_ok=True)

    if (PASTA_MODELOS / f"{nome_da_voz}.onnx").exists():
        print(f"A voz '{nome_da_voz}' já está baixada.")
        return 0

    print(f"Baixando '{nome_da_voz}' para {PASTA_MODELOS}...")
    try:
        download_voice(nome_da_voz, PASTA_MODELOS)
    except Exception as erro:
        print(f"\nNão consegui baixar '{nome_da_voz}': {erro}", file=sys.stderr)
        print("Veja os nomes válidos com:  python scripts/baixar_voz.py --listar", file=sys.stderr)
        return 1

    print(f'Pronto. Teste com:  python -m jarvis --dizer "bom dia"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
