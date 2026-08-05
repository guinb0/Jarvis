"""Comandos de voz ligados ao GitHub."""

from __future__ import annotations

from .. import github_cliente as gh
from .base import Comando


def _cliente(config: dict) -> gh.Cliente:
    return gh.Cliente(config)


class ProjetosGitHub(Comando):
    nome = "projetos github"
    descricao = "Lista seus repos: 'meus projetos', 'meus repositórios'."
    gatilhos = (
        "meus projetos",
        "meu projeto",
        "meus repositorios",
        "meu repositorio",
        "projetos do github",
        "repositorios do github",
        "quais sao meus projetos",
        "lista de projetos",
        "listar projetos",
    )

    def executar(self, frase: str, config: dict) -> str:
        try:
            cliente = _cliente(config)
            repos = cliente.repositorios()
            try:
                from .. import memoria as modulo_memoria

                mem = modulo_memoria.carregar(config)
                cliente.sincronizar_projetos_na_memoria(mem)
            except Exception:
                pass
        except gh.GitHubErro as erro:
            return str(erro)
        return gh.falar_projetos(repos, config["tratamento"])


class StatusGitHub(Comando):
    nome = "github"
    descricao = "Resumo do GitHub: 'status do github', 'tem algo no github'."
    gatilhos = (
        "status do github",
        "resumo do github",
        "tem algo no github",
        "o que tem no github",
        "github",
        "meu github",
    )

    def executar(self, frase: str, config: dict) -> str:
        try:
            dados = _cliente(config).resumo()
        except gh.GitHubErro as erro:
            return str(erro)
        return gh.falar_resumo(dados, config["tratamento"])


class NotificacoesGitHub(Comando):
    nome = "notificacoes github"
    descricao = "Notificações do GitHub: 'notificações do github'."
    gatilhos = (
        "notificacoes do github",
        "notificacao do github",
        "avisos do github",
        "notificacoes github",
    )

    def executar(self, frase: str, config: dict) -> str:
        try:
            notas = _cliente(config).notificacoes(nao_lidas=True)
        except gh.GitHubErro as erro:
            return str(erro)
        return gh.falar_notificacoes(notas, config["tratamento"])


class PullRequestsGitHub(Comando):
    nome = "pull requests"
    descricao = "PRs abertos seus: 'meus pull requests', 'meus prs'."
    gatilhos = (
        "meus pull requests",
        "meu pull request",
        "meus prs",
        "meu pr",
        "pull requests abertos",
        "prs abertos",
    )

    def executar(self, frase: str, config: dict) -> str:
        try:
            prs = _cliente(config).meus_prs()
        except gh.GitHubErro as erro:
            return str(erro)
        return gh.falar_prs(prs, config["tratamento"])


class IssuesGitHub(Comando):
    nome = "issues github"
    descricao = "Issues abertas atribuídas a você: 'minhas issues'."
    gatilhos = (
        "minhas issues",
        "minha issue",
        "issues abertas",
        "issues do github",
    )

    def executar(self, frase: str, config: dict) -> str:
        try:
            issues = _cliente(config).minhas_issues()
        except gh.GitHubErro as erro:
            return str(erro)
        return gh.falar_issues(issues, config["tratamento"])
