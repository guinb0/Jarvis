"""Sincroniza os repositórios do GitHub na memória Postgres (pgvector).

    python scripts/sincronizar_github.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from jarvis.configuracoes import carregar
from jarvis import github_cliente as gh
from jarvis import memoria as modulo_memoria


def main() -> int:
    config = carregar()
    if not (config.get("github_token") or "").strip():
        print("Falta github_token no config.local.json", file=sys.stderr)
        return 1
    mem = modulo_memoria.carregar(config)
    if mem is None:
        print("Postgres indisponível. Rode: docker compose up -d", file=sys.stderr)
        return 1
    try:
        n = gh.Cliente(config).sincronizar_projetos_na_memoria(mem)
    except gh.GitHubErro as erro:
        print(erro, file=sys.stderr)
        return 1
    print(f"{n} trechos de projetos no Postgres. Total: {mem.contar()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
