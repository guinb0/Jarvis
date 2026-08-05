"""Cliente GitHub (REST API) para o Jarvis.

Token em config.local.json (`github_token`) — Personal Access Token classic
com escopos: notifications, repo (ou public_repo).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .configuracoes import RAIZ

API = "https://api.github.com"
API_VERSION = "2022-11-28"


class GitHubErro(Exception):
    """Falha ao falar com a API ou com a configuração do GitHub."""


def _carregar_local() -> dict:
    caminho = RAIZ / "config.local.json"
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


class Cliente:
    def __init__(self, config: dict | None = None):
        local = _carregar_local()
        if config:
            local = {**local, **config}
        self.token = (local.get("github_token") or "").strip()
        if not self.token:
            raise GitHubErro(
                "GitHub ainda não autorizado. Crie um token em "
                "https://github.com/settings/tokens e coloque "
                "github_token no config.local.json."
            )

    def _pedido(self, caminho: str, params: dict | None = None) -> Any:
        url = f"{API}{caminho}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "Jarvis-Assistente",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode(errors="replace")
            if erro.code == 401:
                raise GitHubErro(
                    "Token do GitHub inválido ou sem permissão. Gere outro em "
                    "https://github.com/settings/tokens"
                ) from erro
            raise GitHubErro(f"GitHub {caminho} → {erro.code}: {detalhe}") from erro

    def eu(self) -> dict:
        return self._pedido("/user")

    def notificacoes(self, nao_lidas: bool = True, limite: int = 10) -> list[dict]:
        params = {"per_page": str(limite), "all": "false" if nao_lidas else "true"}
        dados = self._pedido("/notifications", params)
        return dados if isinstance(dados, list) else []

    def meus_prs(self, limite: int = 10) -> list[dict]:
        """PRs abertos criados por mim."""
        login = self.eu().get("login", "")
        q = f"is:pr is:open author:{login}"
        dados = self._pedido(
            "/search/issues",
            {"q": q, "per_page": str(limite), "sort": "updated"},
        )
        return list(dados.get("items") or [])

    def minhas_issues(self, limite: int = 10) -> list[dict]:
        """Issues abertas atribuídas a mim."""
        login = self.eu().get("login", "")
        q = f"is:issue is:open assignee:{login}"
        dados = self._pedido(
            "/search/issues",
            {"q": q, "per_page": str(limite), "sort": "updated"},
        )
        return list(dados.get("items") or [])

    def resumo(self) -> dict:
        notas = self.notificacoes(nao_lidas=True, limite=20)
        prs = self.meus_prs(limite=10)
        issues = self.minhas_issues(limite=10)
        repos = self.repositorios()
        return {
            "login": self.eu().get("login", ""),
            "notificacoes": notas,
            "prs": prs,
            "issues": issues,
            "repositorios": repos,
        }

    def repositorios(self) -> list[dict]:
        """Todos os repos acessíveis (dono, collab, org), paginados."""
        todos: list[dict] = []
        pagina = 1
        while True:
            lote = self._pedido(
                "/user/repos",
                {
                    "per_page": "100",
                    "page": str(pagina),
                    "sort": "updated",
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            if not isinstance(lote, list) or not lote:
                break
            todos.extend(lote)
            if len(lote) < 100:
                break
            pagina += 1
        return todos

    def sincronizar_projetos_na_memoria(self, memoria=None) -> int:
        """Grava os repos na tabela memorias (Postgres/pgvector), não em .md."""
        from . import memoria as modulo_memoria

        repos = self.repositorios()
        login = self.eu().get("login", "")
        trechos: list[str] = [
            f"Conta GitHub: {login}. Total: {len(repos)} repositórios "
            "(próprios, colaboração e organizações)."
        ]
        for r in repos:
            nome = r.get("full_name") or r.get("name") or "?"
            desc = (r.get("description") or "").strip() or "sem descrição"
            lang = r.get("language") or "linguagem não informada"
            priv = "privado" if r.get("private") else "público"
            url = r.get("html_url") or ""
            bloco = (
                f"Projeto GitHub {nome}. Descrição: {desc}. "
                f"Linguagem: {lang}. Visibilidade: {priv}."
            )
            if url:
                bloco += f" URL: {url}."
            trechos.append(bloco)

        mem = memoria
        if mem is None:
            from .configuracoes import carregar

            mem = modulo_memoria.carregar(carregar())
        if mem is None:
            raise GitHubErro(
                "Memória Postgres indisponível. Suba: docker compose up -d"
            )
        return mem.substituir_origem(
            "github:projetos",
            trechos,
            metadados={"login": login, "total": len(repos)},
        )


def garantir_memoria_projetos(config: dict, memoria=None, max_idade_horas: float = 24) -> bool:
    """Atualiza os repos no Postgres se a origem estiver vazia ou velha."""
    from datetime import datetime, timezone

    if not (config.get("github_token") or "").strip():
        return False
    if not config.get("github_sincronizar_projetos", True):
        return False
    if memoria is None:
        return False

    try:
        with memoria._conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT count(*), max(atualizado_em)
                    FROM memorias WHERE origem = %s
                    """,
                    ("github:projetos",),
                )
                qtd, ultimo = cur.fetchone()
    except Exception:
        qtd, ultimo = 0, None

    if qtd and ultimo is not None:
        if getattr(ultimo, "tzinfo", None) is None:
            ultimo = ultimo.replace(tzinfo=timezone.utc)
        idade_h = (datetime.now(timezone.utc) - ultimo).total_seconds() / 3600
        if idade_h < max_idade_horas:
            return False

    try:
        n = Cliente(config).sincronizar_projetos_na_memoria(memoria)
        print(f"[github] {n} trechos de projetos no Postgres", file=sys.stderr)
        return True
    except GitHubErro as erro:
        print(f"[github] não sincronizei projetos: {erro}", file=sys.stderr)
        return False


def _titulo_notificacao(n: dict) -> str:
    assunto = n.get("subject") or {}
    tipo = assunto.get("type") or "aviso"
    titulo = assunto.get("title") or "sem título"
    repo = ((n.get("repository") or {}).get("full_name")) or ""
    if repo:
        return f"{titulo} em {repo}"
    return f"{titulo} ({tipo})"


def falar_notificacoes(notas: list[dict], tratamento: str, limite: int = 5) -> str:
    if not notas:
        return f"Nenhuma notificação nova no GitHub, {tratamento}."
    nomes = [_titulo_notificacao(n) for n in notas[:limite]]
    if len(notas) == 1:
        return f"Você tem uma notificação: {nomes[0]}."
    if len(notas) <= limite:
        corpo = ", ".join(nomes[:-1]) + f" e {nomes[-1]}"
        return f"Você tem {len(notas)} notificações: {corpo}."
    return (
        f"Você tem {len(notas)} notificações. As primeiras: "
        + ", ".join(nomes)
        + f". E mais {len(notas) - limite}."
    )


def falar_prs(prs: list[dict], tratamento: str, limite: int = 5) -> str:
    if not prs:
        return f"Nenhum pull request aberto seu, {tratamento}."
    nomes = []
    for p in prs[:limite]:
        titulo = p.get("title") or "sem título"
        repo = (p.get("repository_url") or "").rstrip("/").split("/")[-1]
        nomes.append(f"{titulo}" + (f" em {repo}" if repo else ""))
    if len(prs) == 1:
        return f"Você tem um pull request aberto: {nomes[0]}."
    if len(prs) <= limite:
        return (
            f"Você tem {len(prs)} pull requests abertos: "
            + ", ".join(nomes[:-1])
            + f" e {nomes[-1]}."
        )
    return (
        f"Você tem {len(prs)} pull requests abertos. Entre eles: "
        + ", ".join(nomes)
        + "."
    )


def falar_issues(issues: list[dict], tratamento: str, limite: int = 5) -> str:
    if not issues:
        return f"Nenhuma issue aberta atribuída a você, {tratamento}."
    nomes = [i.get("title") or "sem título" for i in issues[:limite]]
    if len(issues) == 1:
        return f"Você tem uma issue aberta: {nomes[0]}."
    if len(issues) <= limite:
        return (
            f"Você tem {len(issues)} issues abertas: "
            + ", ".join(nomes[:-1])
            + f" e {nomes[-1]}."
        )
    return (
        f"Você tem {len(issues)} issues abertas. Entre elas: "
        + ", ".join(nomes)
        + "."
    )


def falar_resumo(dados: dict, tratamento: str) -> str:
    n_notas = len(dados.get("notificacoes") or [])
    n_prs = len(dados.get("prs") or [])
    n_issues = len(dados.get("issues") or [])
    n_repos = len(dados.get("repositorios") or [])
    login = dados.get("login") or "sua conta"

    if n_notas == 0 and n_prs == 0 and n_issues == 0 and n_repos == 0:
        return f"GitHub limpo, {tratamento}: nada em {login}."

    partes = [f"No GitHub ({login}), {tratamento}:"]
    if n_repos:
        partes.append(
            f"{n_repos} projeto{'s' if n_repos != 1 else ''} no total."
        )
    if n_notas:
        if n_notas == 1:
            partes.append("1 notificação não lida.")
        else:
            partes.append(f"{n_notas} notificações não lidas.")
    if n_prs:
        if n_prs == 1:
            partes.append("1 pull request aberto.")
        else:
            partes.append(f"{n_prs} pull requests abertos.")
    if n_issues:
        if n_issues == 1:
            partes.append("1 issue atribuída.")
        else:
            partes.append(f"{n_issues} issues atribuídas.")

    if n_notas == 0 and n_prs == 0 and n_issues == 0:
        partes.append("Nada pendente agora.")

    extras = []
    notas = dados.get("notificacoes") or []
    if notas:
        extras.append(_titulo_notificacao(notas[0]))
    prs = dados.get("prs") or []
    if prs:
        extras.append(prs[0].get("title") or "um PR")
    repos = dados.get("repositorios") or []
    if repos:
        extras.append(f"repo recente {repos[0].get('name') or repos[0].get('full_name')}")
    if extras:
        partes.append("Por exemplo: " + "; ".join(extras) + ".")
    return " ".join(partes)


def falar_projetos(repos: list[dict], tratamento: str, limite: int = 8) -> str:
    if not repos:
        return f"Não achei repositórios na sua conta, {tratamento}."
    nomes = []
    for r in repos[:limite]:
        nome = r.get("name") or r.get("full_name") or "?"
        lang = r.get("language")
        if lang:
            nomes.append(f"{nome} em {lang}")
        else:
            nomes.append(nome)
    if len(repos) == 1:
        return f"Você tem um projeto: {nomes[0]}."
    if len(repos) <= limite:
        return (
            f"Você tem {len(repos)} projetos: "
            + ", ".join(nomes[:-1])
            + f" e {nomes[-1]}."
        )
    return (
        f"Você tem {len(repos)} projetos no GitHub. Os mais recentes: "
        + ", ".join(nomes)
        + f". E mais {len(repos) - limite}."
    )
