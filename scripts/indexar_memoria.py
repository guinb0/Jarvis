"""Semeia / inspeciona a memória vetorial no Postgres (pgvector).

    docker compose up -d
    python scripts/indexar_memoria.py              # migra estilo/preferencias se vazios
    python scripts/indexar_memoria.py --buscar "como falar"
    python scripts/indexar_memoria.py --adicionar estilo "Nunca use emoji."
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from jarvis.configuracoes import carregar
from jarvis import memoria as modulo_memoria


SEMENTES = {
    "estilo": RAIZ / "memoria" / "estilo.md",
    "preferencias": RAIZ / "memoria" / "preferencias.md",
}


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Memória vetorial do Jarvis no Postgres."
    )
    analisador.add_argument("--buscar", metavar="FRASE")
    analisador.add_argument(
        "--adicionar",
        nargs=2,
        metavar=("ORIGEM", "TEXTO"),
        help="insere um texto na origem indicada",
    )
    analisador.add_argument(
        "--reseed",
        action="store_true",
        help="reescreve estilo/preferencias a partir dos .md de semente (uma vez)",
    )
    args = analisador.parse_args()

    if not modulo_memoria.disponivel():
        print("Falta fastembed/psycopg. pip install -r requirements.txt", file=sys.stderr)
        return 1

    config = carregar()
    mem = modulo_memoria.carregar(config)
    if mem is None:
        print("Não conectou no Postgres. Rode: docker compose up -d", file=sys.stderr)
        return 1

    if args.buscar:
        for a in mem.buscar(args.buscar):
            print(f"\n[{a['origem']}] similaridade={a['similaridade']}")
            print(a["texto"][:500])
        return 0

    if args.adicionar:
        origem, texto = args.adicionar
        n = mem.adicionar(origem, texto)
        print(f"{n} trecho(s) em '{origem}'. Total: {mem.contar()}")
        return 0

    # Seed inicial: se a origem estiver vazia, lê o .md antigo (só como semente).
    for origem, caminho in SEMENTES.items():
        if mem.contar(origem) and not args.reseed:
            continue
        if not caminho.exists():
            continue
        texto = caminho.read_text(encoding="utf-8")
        pedacos = modulo_memoria._partir(texto) or [texto.strip()]
        n = mem.substituir_origem(origem, pedacos)
        print(f"Semente '{origem}': {n} trechos.")

    print(f"Total na tabela memorias: {mem.contar()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
