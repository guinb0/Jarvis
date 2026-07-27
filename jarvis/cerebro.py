"""Roteamento de comandos: recebe uma frase e decide o que fazer com ela."""

from __future__ import annotations

from .comandos import COMANDOS
from .configuracoes import carregar


class Cerebro:
    """Casa a frase do usuário com o primeiro comando que souber respondê-la."""

    def __init__(self):
        self.config = carregar()
        self.comandos = list(COMANDOS)

    def responder(self, frase: str) -> str:
        frase_limpa = frase.strip()
        if not frase_limpa:
            return "Não entendi, " + self.config["tratamento"] + "."

        for comando in self.comandos:
            if comando.aceita(frase_limpa):
                return comando.executar(frase_limpa, self.config)

        return (
            f"Ainda não sei fazer isso, {self.config['tratamento']}. "
            "Diga 'ajuda' para ver o que eu entendo."
        )
