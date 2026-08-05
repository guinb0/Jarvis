"""Comandos de tarefas via TickTick."""

from __future__ import annotations

import re
from datetime import date, timedelta

from .. import ticktick
from .base import Comando, normalizar


def _cliente(config: dict) -> ticktick.Cliente:
    return ticktick.Cliente(config)


def _extrair_titulo(frase: str, gatilhos: tuple[str, ...]) -> str:
    texto = frase.strip()
    for g in sorted(gatilhos, key=len, reverse=True):
        padrao = rf"^\s*{re.escape(g)}\s*[:\-]?\s*"
        novo = re.sub(padrao, "", texto, count=1, flags=re.IGNORECASE)
        if novo != texto:
            return novo.strip(" .")
    return texto


# Prefixos naturais de "já fiz" — usados no aceita e na extração.
_PREFIXOS_CONCLUSAO = (
    "concluir tarefa",
    "conclui tarefa",
    "marcar como feita",
    "marca como feita",
    "marquei como feita",
    "tarefa feita",
    "ja fiz a tarefa",
    "ja fiz o",
    "ja fiz a",
    "ja fiz",
    "ja bebi",
    "ja terminei",
    "ja acabei",
    "ja completei",
    "completei",
    "terminei de",
    "terminei",
    "acabei de",
    "acabei",
    "fiz a tarefa",
    "fiz a",
    "fiz o",
)


class ListarTarefas(Comando):
    nome = "tarefas"
    descricao = "Lista tarefas do TickTick: 'tarefas de hoje', 'minhas tarefas'."
    gatilhos = (
        "minhas tarefas",
        "tarefas de hoje",
        "tarefa de hoje",
        "o que eu tenho pra hoje",
        "o que eu tenho para hoje",
        "o que tenho pra hoje",
        "lista de tarefas",
        "listar tarefas",
        "tarefas ticktick",
        "ticktick",
    )

    def executar(self, frase: str, config: dict) -> str:
        try:
            cliente = _cliente(config)
            todas = cliente.tarefas_ativas()
        except ticktick.TickTickErro as erro:
            return str(erro)

        normal = normalizar(frase)
        if "hoje" in normal:
            lista = ticktick.tarefas_de_hoje(todas)
            if not lista:
                return f"Nada com prazo pra hoje, {config['tratamento']}."
            return ticktick.falar_lista(lista, config["tratamento"])

        atrasadas = ticktick.tarefas_atrasadas(todas)
        hoje = ticktick.tarefas_de_hoje(todas)
        prioridade = atrasadas + [t for t in hoje if t not in atrasadas]
        lista = prioridade or todas
        return ticktick.falar_lista(lista, config["tratamento"])


class CriarTarefa(Comando):
    nome = "criar tarefa"
    descricao = "Cria tarefa no TickTick: 'criar tarefa comprar cafe'."
    gatilhos = (
        "criar tarefa",
        "cria tarefa",
        "adicionar tarefa",
        "adiciona tarefa",
        "nova tarefa",
        "anota tarefa",
        "lembra de",
        "me lembra de",
    )

    def executar(self, frase: str, config: dict) -> str:
        titulo = _extrair_titulo(frase, self.gatilhos)
        if not titulo:
            return f"Qual o título da tarefa, {config['tratamento']}?"

        due = None
        normal = normalizar(titulo)
        if normal.endswith(" amanha") or " amanha" in f" {normal} ":
            due = date.today() + timedelta(days=1)
            titulo = re.sub(
                r"\s+amanh[aã]\s*$", "", titulo, flags=re.IGNORECASE
            ).strip()
        elif re.search(r"\bhoje\b", normal):
            due = date.today()
            titulo = re.sub(r"\s+hoje\s*$", "", titulo, flags=re.IGNORECASE).strip()

        try:
            cliente = _cliente(config)
            cliente.criar_tarefa(titulo, due=due)
        except ticktick.TickTickErro as erro:
            return str(erro)

        quando = ""
        if due == date.today():
            quando = " pra hoje"
        elif due is not None:
            quando = " pra amanhã"
        return f"Anotei: {titulo}{quando}, {config['tratamento']}."


class ConcluirTarefa(Comando):
    nome = "concluir tarefa"
    descricao = "Conclui no TickTick: 'já fiz atividade', 'já bebi água', 'concluir tarefa X'."
    gatilhos = _PREFIXOS_CONCLUSAO

    def aceita(self, frase: str) -> bool:
        if super().aceita(frase):
            return True
        # "já bebi a água", "fiz atividade física do dia"
        n = normalizar(frase)
        return bool(
            re.search(
                r"\b(ja\s+(fiz|bebi|terminei|acabei|completei)|"
                r"fiz\s+(a|o)\s+\w|"
                r"bebi\s+\w)",
                n,
            )
        )

    def executar(self, frase: str, config: dict) -> str:
        pedido = _extrair_titulo(frase, self.gatilhos)
        pedido = re.sub(
            r"^(a\s+)?tarefa\s+", "", pedido, flags=re.IGNORECASE
        ).strip()
        # "isso" / vazio = tenta a única pendente prioritária
        vago = normalizar(pedido) in {"", "isso", "aquilo", "ela", "ele"}

        try:
            cliente = _cliente(config)
            todas = cliente.tarefas_ativas()
            if not todas:
                return f"Não há tarefas abertas, {config['tratamento']}."

            if vago:
                atrasadas = ticktick.tarefas_atrasadas(todas)
                hoje = ticktick.tarefas_de_hoje(todas)
                prioridade = atrasadas + [t for t in hoje if t not in atrasadas]
                candidatas = prioridade or todas
                if len(candidatas) == 1:
                    tarefa = candidatas[0]
                else:
                    nomes = ", ".join(
                        (t.get("title") or "?") for t in candidatas[:4]
                    )
                    return (
                        f"Qual delas, {config['tratamento']}? "
                        f"Tenho: {nomes}."
                    )
            else:
                tarefa = ticktick.achar_tarefa(todas, pedido)
                if not tarefa:
                    return f"Não achei a tarefa '{pedido}'."

            cliente.concluir(
                tarefa["projectId"],
                tarefa["id"],
                titulo=tarefa.get("title") or "",
            )
        except ticktick.TickTickErro as erro:
            return str(erro)

        return f"Concluída: {tarefa.get('title')}, {config['tratamento']}."


class RelatorioProdutividade(Comando):
    nome = "relatorio"
    descricao = (
        "Relatório semanal do TickTick: 'relatório da semana', 'minha produtividade'."
    )
    gatilhos = (
        "relatorio da semana",
        "relatorio semanal",
        "resumo da semana",
        "resumo semanal",
        "minha produtividade",
        "produtividade da semana",
        "como foi minha semana",
        "como esta minha semana",
        "o que eu fiz essa semana",
        "o que eu fiz esta semana",
        "o que fiz essa semana",
        "acompanhamento da semana",
    )

    def executar(self, frase: str, config: dict) -> str:
        try:
            return ticktick.gerar_relatorio(config)
        except ticktick.TickTickErro as erro:
            return str(erro)
