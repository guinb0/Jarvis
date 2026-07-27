"""Comandos básicos: saudação, hora, data e ajuda."""

from __future__ import annotations

from datetime import datetime

from .base import Comando, PedidoDeEncerramento

DIAS = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def periodo_do_dia(hora: int) -> str:
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


class Saudacao(Comando):
    nome = "saudação"
    descricao = "Cumprimenta de volta conforme a hora do dia."
    gatilhos = ("ola", "olá", "oi", "bom dia", "boa tarde", "boa noite", "e ai")

    def executar(self, frase: str, config: dict) -> str:
        agora = datetime.now()
        return f"{periodo_do_dia(agora.hour)}, {config['tratamento']}. Em que posso ajudar?"


class Horas(Comando):
    nome = "horas"
    descricao = "Informa a hora atual."
    gatilhos = ("que horas", "hora certa", "horario")

    def executar(self, frase: str, config: dict) -> str:
        agora = datetime.now()
        return f"São {agora.hour} horas e {agora.minute} minutos, {config['tratamento']}."


class Data(Comando):
    nome = "data"
    descricao = "Informa o dia de hoje por extenso."
    gatilhos = ("que dia", "data de hoje", "hoje e dia")

    def executar(self, frase: str, config: dict) -> str:
        hoje = datetime.now()
        return (
            f"Hoje é {DIAS[hoje.weekday()]}, "
            f"{hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}."
        )


class Ajuda(Comando):
    nome = "ajuda"
    descricao = "Lista tudo que o Jarvis entende."
    gatilhos = ("ajuda", "o que voce faz", "comandos")

    def executar(self, frase: str, config: dict) -> str:
        from . import COMANDOS

        linhas = [f"- {c.nome}: {c.descricao}" for c in COMANDOS]
        return "Eu entendo o seguinte:\n" + "\n".join(linhas)


class Encerrar(Comando):
    nome = "encerrar"
    descricao = "Desliga o assistente."
    gatilhos = ("desligar", "encerrar", "tchau", "ate logo", "sair")

    def executar(self, frase: str, config: dict) -> str:
        raise PedidoDeEncerramento(f"Até logo, {config['tratamento']}.")
