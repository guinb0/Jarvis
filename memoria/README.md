# Memória (sementes opcionais)

O índice real fica no **Postgres + pgvector** (`docker compose up -d`).

Os `.md` aqui só servem como semente na primeira carga:

```bash
docker compose up -d
python scripts/indexar_memoria.py
python scripts/indexar_memoria.py --adicionar preferencias "Prefere respostas curtas."
python scripts/indexar_memoria.py --buscar "como deve falar"
```

Conexão padrão: `postgresql://jarvis:jarvis@127.0.0.1:5433/jarvis`
