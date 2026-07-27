"""Contrato que todo comando do Jarvis segue."""

from __future__ import annotations

import re
import unicodedata


class PedidoDeEncerramento(Exception):
    """Levantada por um comando que pede o desligamento do assistente.

    A mensagem da exceção é a despedida a ser falada antes de sair.
    """


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação — para comparar frases faladas."""
    sem_acento = "".join(
        letra
        for letra in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(letra) != "Mn"
    )
    return re.sub(r"[^\w\s]", " ", sem_acento).strip()


class Comando:
    """Base dos comandos. Subclasses definem `gatilhos` e `executar`."""

    nome: str = ""
    descricao: str = ""
    gatilhos: tuple[str, ...] = ()

    def aceita(self, frase: str) -> bool:
        # Limites de palavra evitam que gatilhos curtos ("oi") casem dentro de
        # outras palavras ("depois").
        frase_normalizada = normalizar(frase)
        return any(
            re.search(rf"\b{re.escape(normalizar(g))}\b", frase_normalizada)
            for g in self.gatilhos
        )

    def executar(self, frase: str, config: dict) -> str:
        raise NotImplementedError
