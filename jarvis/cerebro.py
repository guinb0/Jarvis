"""Roteamento de comandos: recebe uma frase e decide o que fazer com ela."""

from __future__ import annotations

import difflib

from .comandos import COMANDOS, normalizar
from .configuracoes import carregar

# Quão parecida com "jarvis" uma palavra precisa ser para contar como chamado.
# O Whisper erra o nome com frequência, e uma comparação exata deixaria o
# assistente mudo justamente quando chamado. 0,70 foi medido: pega "javis",
# "jarves", "jarvi", "harvis" e não dispara em nenhuma palavra comum. Abaixo
# disso "várias" passaria a acordá-lo, que é o incômodo que queremos evitar.
SEMELHANCA_MINIMA = 0.7

# Erros de transcrição que empatam em semelhança com palavras do dia a dia, e
# por isso não dá para pegar baixando o limiar. Só entram aqui grafias que não
# são palavras usadas em conversa.
VARIACOES_CONHECIDAS = frozenset({"jarvez", "jarbas", "jarviss", "tcharvis"})

# Erros recorrentes do Whisper em português — corrigidos antes de casar comando.
CORRECOES_STT = (
    (r"\btudo de web\b", "tudo bem"),
    (r"\btudo de bem\b", "tudo bem"),
    (r"\btudo de ve\b", "tudo bem"),
    (r"\btudo de ver\b", "tudo bem"),
    (r"\bjavis\b", "jarvis"),
    (r"\bjarves\b", "jarvis"),
)


def _e_a_ativacao(palavra: str, ativacao: str) -> bool:
    """Diz se uma palavra falada é o nome do assistente, mesmo mal transcrito."""
    if not palavra:
        return False
    if palavra == ativacao or palavra in VARIACOES_CONHECIDAS:
        return True
    return difflib.SequenceMatcher(None, palavra, ativacao).ratio() >= SEMELHANCA_MINIMA


def corrigir_transcricao(frase: str) -> str:
    """Aplica correções conhecidas de STT sem alterar o restante."""
    import re

    corrigida = frase
    for padrao, troca in CORRECOES_STT:
        corrigida = re.sub(padrao, troca, corrigida, flags=re.IGNORECASE)
    return corrigida


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
        que provavelmente era conversa alheia, TV ou som de jogo.
        """
        ativacao = normalizar(self.config["palavra_de_ativacao"])
        palavras = frase.split()

        # Compara palavra a palavra para poder devolver o texto original, com
        # acentos, em vez da versão normalizada que o Claude receberia torta.
        restantes = [p for p in palavras if not _e_a_ativacao(normalizar(p), ativacao)]

        if len(restantes) < len(palavras):
            return " ".join(restantes).strip(" ,.!?")  # foi chamado

        if self.config["exigir_palavra_de_ativacao"]:
            return None

        return frase

    def responder_em_partes(self, frase: str):
        """Mesma coisa que `responder`, mas entregando a resposta em pedaços.

        Comando local resolve na hora e sai inteiro. Só a conversa com o Claude
        chega em partes, que é onde a espera existe.
        """
        frase_limpa = corrigir_transcricao(frase.strip())
        if not frase_limpa:
            yield f"Pois não, {self.config['tratamento']}?"
            return

        for comando in self.comandos:
            if not comando.aceita(frase_limpa):
                continue
            if comando.nome == "pesquisar" and self.conversa:
                break
            yield comando.executar(frase_limpa, self.config)
            return

        if self.conversa:
            yield from self.conversa.responder_em_partes(frase_limpa)
            return

        yield (
            f"Ainda não sei fazer isso, {self.config['tratamento']}. "
            "Diga 'ajuda' para ver o que eu entendo."
        )

    def responder(self, frase: str) -> str:
        frase_limpa = corrigir_transcricao(frase.strip())
        if not frase_limpa:
            # Chamaram pelo nome e pararam aí: é um "oi", não um erro.
            return f"Pois não, {self.config['tratamento']}?"

        for comando in self.comandos:
            if not comando.aceita(frase_limpa):
                continue
            # Com a conversa aberta, "pesquisar X" vai para o Claude: ele busca,
            # responde em voz e abre as fontes. O comando local só abre o Google
            # quando não há nuvem — senão a pesquisa ficaria muda.
            if comando.nome == "pesquisar" and self.conversa:
                break
            return comando.executar(frase_limpa, self.config)

        # Nenhum comando local serviu: manda para o modelo de linguagem.
        if self.conversa:
            return self.conversa.responder(frase_limpa)

        return (
            f"Ainda não sei fazer isso, {self.config['tratamento']}. "
            "Diga 'ajuda' para ver o que eu entendo."
        )
