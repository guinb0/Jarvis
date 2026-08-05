"""Memória vetorial local, em SQLite.

Um arquivo só (`modelos/memoria.db`), sem servidor e sem Docker. Embeddings
gerados na CPU com fastembed; a busca por similaridade roda em numpy.

POR QUE NÃO PGVECTOR
    A versão anterior usava Postgres com pgvector via Docker. Funcionava, mas
    exigia o Docker Desktop de pé — e quando ele não estava, a memória
    simplesmente não subia. Para o volume de um assistente pessoal (milhares de
    trechos, não milhões) o índice aproximado do pgvector não compra nada:
    comparar 10 mil vetores de 384 dimensões em numpy leva menos de 10 ms.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Multilíngue, 384 dimensões.
MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSOES = 384

TAMANHO_MAXIMO_DO_TRECHO = 700
SOBREPOSICAO = 80


def disponivel() -> bool:
    """SQLite vem com o Python; só o gerador de embeddings é externo."""
    try:
        import fastembed  # noqa: F401
    except ImportError:
        return False
    return True


def _partir(texto: str) -> list[str]:
    texto = texto.replace("\r\n", "\n").strip()
    if not texto:
        return []
    blocos = (
        re.split(r"(?=\n#{1,3}\s)", texto)
        if re.search(r"(?m)^#{1,3}\s", texto)
        else texto.split("\n\n")
    )
    trechos: list[str] = []
    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue
        if len(bloco) <= TAMANHO_MAXIMO_DO_TRECHO:
            trechos.append(bloco)
            continue
        inicio = 0
        while inicio < len(bloco):
            fim = min(inicio + TAMANHO_MAXIMO_DO_TRECHO, len(bloco))
            pedaco = bloco[inicio:fim].strip()
            if pedaco:
                trechos.append(pedaco)
            if fim >= len(bloco):
                break
            inicio = max(fim - SOBREPOSICAO, inicio + 1)
    return trechos


class Memoria:
    """Busca por similaridade sobre a tabela `memorias` num arquivo SQLite."""

    def __init__(
        self,
        caminho: str | Path,
        modelo: str = MODELO_EMBEDDING,
        resultados: int = 3,
        limiar: float = 0.25,
    ):
        if not disponivel():
            raise ImportError(
                "falta o fastembed. Rode: pip install -r requirements.txt"
            )

        from fastembed import TextEmbedding

        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.resultados = resultados
        self.limiar = limiar
        self._embedder = TextEmbedding(model_name=modelo)

        # Matriz de vetores mantida em memória: evita reler o banco a cada
        # busca. Zerada em qualquer escrita.
        self._cache: tuple[np.ndarray, list[tuple]] | None = None

        self._garantir_schema()

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.caminho, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")  # leitura não trava na escrita
        return conn

    def _garantir_schema(self) -> None:
        with self._conectar() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memorias (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    origem        TEXT NOT NULL,
                    texto         TEXT NOT NULL,
                    embedding     BLOB NOT NULL,
                    metadados     TEXT NOT NULL DEFAULT '{}',
                    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS memorias_origem_idx ON memorias (origem)"
            )

    def _embed(self, textos: list[str]) -> np.ndarray:
        """Vetores normalizados: com norma 1, cosseno vira produto escalar."""
        matriz = np.asarray(list(self._embedder.embed(textos)), dtype=np.float32)
        if matriz.ndim == 1:
            matriz = matriz.reshape(1, -1)
        normas = np.maximum(np.linalg.norm(matriz, axis=1, keepdims=True), 1e-12)
        return matriz / normas

    def _carregar_tudo(self) -> tuple[np.ndarray, list[tuple]]:
        """Lê o banco inteiro para a memória, uma vez, e guarda."""
        if self._cache is not None:
            return self._cache

        with self._conectar() as conn:
            linhas = conn.execute(
                "SELECT origem, texto, metadados, embedding FROM memorias"
            ).fetchall()

        if not linhas:
            self._cache = (np.zeros((0, DIMENSOES), dtype=np.float32), [])
            return self._cache

        vetores = np.vstack(
            [np.frombuffer(linha[3], dtype=np.float32) for linha in linhas]
        )
        self._cache = (vetores, [(l[0], l[1], l[2]) for l in linhas])
        return self._cache

    def contar(self, origem: str | None = None) -> int:
        with self._conectar() as conn:
            if origem:
                cur = conn.execute(
                    "SELECT count(*) FROM memorias WHERE origem = ?", (origem,)
                )
            else:
                cur = conn.execute("SELECT count(*) FROM memorias")
            return int(cur.fetchone()[0])

    def _inserir(self, conn, origem: str, textos: list[str], meta: dict) -> None:
        vetores = self._embed(textos)
        conn.executemany(
            "INSERT INTO memorias (origem, texto, embedding, metadados) "
            "VALUES (?, ?, ?, ?)",
            [
                (origem, texto, vetor.tobytes(), json.dumps(meta, ensure_ascii=False))
                for texto, vetor in zip(textos, vetores, strict=True)
            ],
        )
        self._cache = None

    def substituir_origem(
        self,
        origem: str,
        textos: list[str],
        metadados: dict[str, Any] | None = None,
    ) -> int:
        """Apaga tudo da origem e reinsere os trechos com embedding."""
        limpos = [t.strip() for t in textos if t and t.strip()]
        with self._conectar() as conn:
            conn.execute("DELETE FROM memorias WHERE origem = ?", (origem,))
            self._cache = None
            if not limpos:
                return 0
            self._inserir(conn, origem, limpos, metadados or {})
        return len(limpos)

    def adicionar(
        self,
        origem: str,
        texto: str,
        metadados: dict[str, Any] | None = None,
        *,
        partir: bool = True,
    ) -> int:
        """Acrescenta um texto sem apagar o que a origem já tinha."""
        pedacos = [p for p in (_partir(texto) if partir else [texto.strip()]) if p]
        if not pedacos:
            return 0
        with self._conectar() as conn:
            self._inserir(conn, origem, pedacos, metadados or {})
        return len(pedacos)

    def buscar(self, frase: str) -> list[dict]:
        if not frase.strip():
            return []

        vetores, linhas = self._carregar_tudo()
        if len(linhas) == 0:
            return []

        consulta = self._embed([frase.strip()])[0]
        # Vetores normalizados na gravação: o produto escalar já é o cosseno.
        similaridades = vetores @ consulta

        # argpartition acha os melhores sem ordenar tudo.
        quantos = min(self.resultados * 3, len(linhas))
        candidatos = np.argpartition(-similaridades, quantos - 1)[:quantos]
        candidatos = candidatos[np.argsort(-similaridades[candidatos])]

        achados: list[dict] = []
        for indice in candidatos:
            nota = float(similaridades[indice])
            if nota < self.limiar:
                break  # já vêm ordenados: daqui pra frente só piora
            origem, texto, meta = linhas[indice]
            try:
                meta_dict = json.loads(meta)
            except (ValueError, TypeError):
                meta_dict = {}
            achados.append(
                {
                    "origem": origem,
                    "texto": texto,
                    "metadados": meta_dict if isinstance(meta_dict, dict) else {},
                    "similaridade": round(nota, 3),
                }
            )
            if len(achados) >= self.resultados:
                break
        return achados

    def contexto_para_prompt(self, frase: str) -> str:
        achados = self.buscar(frase)
        if not achados:
            return ""
        partes = [
            f"[{a['origem']} · {a['similaridade']}]\n{a['texto']}" for a in achados
        ]
        return (
            "Memória local do usuário (use se for relevante ao pedido; "
            "não invente além disso; não leia caminhos de arquivo em voz alta):\n"
            + "\n\n---\n\n".join(partes)
        )


def carregar(config: dict) -> Memoria | None:
    if not config.get("usar_memoria", True):
        return None
    if not disponivel():
        print(
            "[memoria] desligada: falta o fastembed. "
            "Rode: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return None

    from .configuracoes import PASTA_MODELOS

    caminho = config.get("memoria_banco") or (PASTA_MODELOS / "memoria.db")
    try:
        mem = Memoria(
            caminho=caminho,
            resultados=int(config.get("memoria_resultados", 3)),
            limiar=float(config.get("memoria_limiar", 0.25)),
            modelo=config.get("memoria_modelo_embedding", MODELO_EMBEDDING),
        )
        print(f"[memoria] {mem.contar()} trechos em {mem.caminho.name}", file=sys.stderr)
        return mem
    except Exception as erro:  # noqa: BLE001
        print(f"[memoria] não abriu {caminho}: {erro}", file=sys.stderr)
        return None
