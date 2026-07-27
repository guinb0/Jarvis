"""Roteamento de comandos: recebe uma frase e decide o que fazer com ela."""

from __future__ import annotations

import re

from .comandos import COMANDOS, normalizar
from .configuracoes import carregar


class Cerebro:
    """Casa a frase do usuário com o primeiro comando que souber respondê-la."""

    def __init__(self, usar_nuvem: bool = True):
        self.config = carregar()
        self.comandos = list(COMANDOS)
        self.conversa = self._abrir_conversa() if usar_nuvem else None

    def _abrir_conversa(self):
        """Liga a conversa aberta com o Claude, se houver credencial."""
        from . import conversa

        if not conversa.disponivel():
            return None

        try:
            return conversa.Conversa(self.config)
        except conversa.SemCredencial:
            # O Jarvis segue funcionando só com os comandos locais.
            return None

    def extrair_pedido(self, frase: str) -> str | None:
        """Remove a palavra de ativação da frase.

        Devolve o pedido sem o "Jarvis" da frente, ou None quando a ativação é
        exigida e a frase não a contém — nesse caso o assistente ignora o áudio,
        que provavelmente era conversa alheia.
        """
        ativacao = normalizar(self.config["palavra_de_ativacao"])
        sem_ativacao = re.sub(rf"\b{re.escape(ativacao)}\b", " ", normalizar(frase)).strip()

        if sem_ativacao != normalizar(frase):
            return sem_ativacao  # a palavra estava lá e foi removida

        if self.config["exigir_palavra_de_ativacao"]:
            return None

        return frase

    def responder(self, frase: str) -> str:
        frase_limpa = frase.strip()
        if not frase_limpa:
            return f"Não entendi, {self.config['tratamento']}."

        for comando in self.comandos:
            if comando.aceita(frase_limpa):
                return comando.executar(frase_limpa, self.config)

        # Nenhum comando local serviu: manda para o modelo de linguagem.
        if self.conversa:
            return self.conversa.responder(frase_limpa)

        return (
            f"Ainda não sei fazer isso, {self.config['tratamento']}. "
            "Diga 'ajuda' para ver o que eu entendo."
        )
