"""Cliente TickTick (Open API) para o Jarvis.

Autenticação OAuth2; tokens ficam em config.local.json (fora do git).
Documentação: https://developer.ticktick.com/
"""

from __future__ import annotations

import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .comandos.base import normalizar
from .configuracoes import RAIZ

API = "https://api.ticktick.com/open/v1"
AUTH_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
ESCOPOS = "tasks:read tasks:write"

# Status 0 = ativa; 2 = concluída (Open API).
STATUS_ATIVA = 0


class TickTickErro(Exception):
    """Falha ao falar com a API ou com a configuração do TickTick."""


def _carregar_local() -> dict:
    caminho = RAIZ / "config.local.json"
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def _salvar_local(atualizacao: dict) -> None:
    caminho = RAIZ / "config.local.json"
    dados = _carregar_local()
    dados.update(atualizacao)
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def url_de_autorizacao(client_id: str) -> str:
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "scope": ESCOPOS,
            "state": "jarvis",
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
        }
    )
    return f"{AUTH_URL}?{params}"


def trocar_codigo_por_token(client_id: str, client_secret: str, code: str) -> dict:
    """Troca o code do OAuth por access_token e grava no config.local.json."""
    corpo = urllib.parse.urlencode(
        {
            "code": code,
            "grant_type": "authorization_code",
            "scope": ESCOPOS,
            "redirect_uri": REDIRECT_URI,
        }
    ).encode()
    basico = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    pedido = urllib.request.Request(
        TOKEN_URL,
        data=corpo,
        headers={
            "Authorization": f"Basic {basico}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resp:
            dados = json.loads(resp.read().decode())
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode(errors="replace")
        raise TickTickErro(f"OAuth falhou ({erro.code}): {detalhe}") from erro

    token = dados.get("access_token")
    if not token:
        raise TickTickErro(f"resposta OAuth sem access_token: {dados}")

    gravar = {
        "ticktick_client_id": client_id,
        "ticktick_client_secret": client_secret,
        "ticktick_access_token": token,
    }
    if dados.get("refresh_token"):
        gravar["ticktick_refresh_token"] = dados["refresh_token"]
    _salvar_local(gravar)
    return dados


class Cliente:
    """Chamadas autenticadas à Open API."""

    def __init__(self, config: dict | None = None):
        local = _carregar_local()
        if config:
            local = {**local, **config}
        self.client_id = local.get("ticktick_client_id", "")
        self.client_secret = local.get("ticktick_client_secret", "")
        self.access_token = local.get("ticktick_access_token", "")
        self.refresh_token = local.get("ticktick_refresh_token", "")
        if not self.access_token:
            raise TickTickErro(
                "TickTick ainda não autorizado. Rode: python scripts/autorizar_ticktick.py"
            )

    def _pedido(self, metodo: str, caminho: str, corpo: dict | None = None) -> Any:
        url = f"{API}{caminho}"
        data = None if corpo is None else json.dumps(corpo).encode()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                bruto = resp.read()
                return json.loads(bruto.decode()) if bruto else {}
        except urllib.error.HTTPError as erro:
            if erro.code == 401 and self._tentar_refresh():
                return self._pedido(metodo, caminho, corpo)
            detalhe = erro.read().decode(errors="replace")
            raise TickTickErro(f"API {metodo} {caminho} → {erro.code}: {detalhe}") from erro

    def _tentar_refresh(self) -> bool:
        if not (self.refresh_token and self.client_id and self.client_secret):
            return False
        corpo = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "scope": ESCOPOS,
            }
        ).encode()
        basico = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        req = urllib.request.Request(
            TOKEN_URL,
            data=corpo,
            headers={
                "Authorization": f"Basic {basico}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados = json.loads(resp.read().decode())
        except urllib.error.HTTPError:
            return False
        token = dados.get("access_token")
        if not token:
            return False
        self.access_token = token
        if dados.get("refresh_token"):
            self.refresh_token = dados["refresh_token"]
        _salvar_local(
            {
                "ticktick_access_token": self.access_token,
                "ticktick_refresh_token": self.refresh_token,
            }
        )
        return True

    def projetos(self) -> list[dict]:
        dados = self._pedido("GET", "/project")
        return dados if isinstance(dados, list) else []

    def dados_do_projeto(self, project_id: str) -> dict:
        return self._pedido("GET", f"/project/{project_id}/data") or {}

    def tarefas_ativas(self) -> list[dict]:
        """Inbox + todos os projetos; só tarefas não concluídas."""
        achadas: list[dict] = []
        vistos: set[str] = set()

        for project_id in self._ids_para_listar():
            try:
                pacote = self.dados_do_projeto(project_id)
            except TickTickErro as erro:
                print(f"[ticktick] pulando {project_id}: {erro}", file=sys.stderr)
                continue
            for tarefa in pacote.get("tasks") or []:
                tid = tarefa.get("id")
                if not tid or tid in vistos:
                    continue
                if int(tarefa.get("status", 0)) != STATUS_ATIVA:
                    continue
                vistos.add(tid)
                achadas.append(tarefa)
        return achadas

    def _ids_para_listar(self) -> list[str]:
        ids = ["inbox"]
        for p in self.projetos():
            pid = p.get("id")
            if pid and pid not in ids:
                ids.append(pid)
        return ids

    def inbox_id(self) -> str:
        """Descobre o id real da inbox a partir de qualquer tarefa nela."""
        try:
            pacote = self.dados_do_projeto("inbox")
        except TickTickErro:
            pacote = {}
        for tarefa in pacote.get("tasks") or []:
            pid = tarefa.get("projectId")
            if pid:
                return pid
        # Sem tarefas na inbox: cria e lê de volta, ou usa o atalho "inbox".
        return "inbox"

    def criar_tarefa(self, titulo: str, due: date | None = None) -> dict:
        corpo: dict[str, Any] = {
            "title": titulo.strip(),
            "projectId": self.inbox_id(),
        }
        if due is not None:
            # Meia-noite local no formato que a API aceita.
            agora = datetime.now().astimezone()
            alvo = datetime(
                due.year, due.month, due.day, 23, 59, 0, tzinfo=agora.tzinfo
            )
            corpo["dueDate"] = alvo.strftime("%Y-%m-%dT%H:%M:%S%z")
            # %z vem sem ':' (ex. -0300); a API aceita esse formato.
            corpo["isAllDay"] = True
            corpo["timeZone"] = str(agora.tzinfo) if agora.tzinfo else "America/Sao_Paulo"
        return self._pedido("POST", "/task", corpo)

    def concluir(self, project_id: str, task_id: str, titulo: str = "") -> None:
        # A rota /complete às vezes devolve 200 sem efeito. Marcar status=2
        # (concluída) no update é o que realmente grava na conta.
        corpo = {
            "id": task_id,
            "projectId": project_id,
            "status": 2,
        }
        if titulo:
            corpo["title"] = titulo
        self._pedido("POST", f"/task/{task_id}", corpo)

    def tarefas_concluidas(
        self, inicio: datetime, fim: datetime, project_ids: list[str] | None = None
    ) -> list[dict]:
        """Tarefas marcadas como feitas no intervalo (inclui recorrentes)."""
        if project_ids is None:
            ids: list[str] = []
            for pid in self._ids_para_listar():
                ids.append(self.inbox_id() if pid == "inbox" else pid)
            if "inbox" not in ids:
                ids.append("inbox")
            project_ids = list(dict.fromkeys(ids))

        # Garante offset no formato +0000 / -0300
        def fmt(dt: datetime) -> str:
            if dt.tzinfo is None:
                dt = dt.astimezone()
            return dt.strftime("%Y-%m-%dT%H:%M:%S%z")

        dados = self._pedido(
            "POST",
            "/task/completed",
            {
                "projectIds": project_ids,
                "startDate": fmt(inicio),
                "endDate": fmt(fim),
            },
        )
        return dados if isinstance(dados, list) else []


def inicio_da_semana(referencia: datetime | None = None) -> datetime:
    """Segunda-feira 00:00 no fuso local."""
    agora = (referencia or datetime.now()).astimezone()
    segunda = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    segunda -= timedelta(days=segunda.weekday())
    return segunda


def montar_relatorio_semana(
    concluidas: list[dict],
    ativas: list[dict],
    tratamento: str,
    *,
    agora: datetime | None = None,
) -> str:
    """Texto curto, pronto para voz, sobre a produtividade da semana."""
    agora = (agora or datetime.now()).astimezone()
    inicio = inicio_da_semana(agora)

    # Só contagens da semana corrente (a API já filtra, mas reforça).
    feitas = []
    for t in concluidas:
        quando = _parse_data_ticktick(t.get("completedTime"))
        if quando is None or quando >= inicio.date():
            feitas.append(t)

    atrasadas = tarefas_atrasadas(ativas, agora.date())

    n_feitas = len(feitas)
    n_abertas = len(ativas)
    n_atraso = len(atrasadas)

    # Títulos mais recorrentes entre as concluídas (hábitos diários sobem).
    contagem: dict[str, int] = {}
    for t in feitas:
        nome = (t.get("title") or "sem título").strip()
        contagem[nome] = contagem.get(nome, 0) + 1
    destaques = sorted(contagem.items(), key=lambda x: (-x[1], x[0]))[:3]

    partes: list[str] = []
    if n_feitas == 0:
        partes.append(
            f"Nesta semana você ainda não concluiu nenhuma tarefa no TickTick, {tratamento}."
        )
    elif n_feitas == 1:
        titulo = feitas[0].get("title") or "sem título"
        partes.append(
            f"Nesta semana você concluiu uma tarefa: {titulo}, {tratamento}."
        )
    else:
        partes.append(
            f"Nesta semana você concluiu {n_feitas} tarefas, {tratamento}."
        )

    if destaques and n_feitas > 1:
        nomes = []
        for nome, qtd in destaques:
            nomes.append(nome if qtd == 1 else f"{nome} ({qtd} vezes)")
        if len(nomes) == 1:
            partes.append(f"Destaque: {nomes[0]}.")
        else:
            partes.append(
                "Destaques: " + ", ".join(nomes[:-1]) + f" e {nomes[-1]}."
            )

    if n_abertas == 0:
        partes.append("Não há nada pendente agora.")
    else:
        abertos = [t.get("title") or "sem título" for t in ativas[:3]]
        if n_atraso:
            partes.append(
                f"Em aberto: {n_abertas} pendentes, sendo {n_atraso} atrasada"
                f"{'s' if n_atraso > 1 else ''}."
            )
        else:
            partes.append(
                f"Em aberto: {n_abertas} pendente{'s' if n_abertas > 1 else ''}."
            )
        if len(ativas) == 1:
            partes.append(f"Em andamento: {abertos[0]}.")
        elif len(ativas) <= 3:
            partes.append(
                "Em andamento: " + ", ".join(abertos[:-1]) + f" e {abertos[-1]}."
            )
        else:
            partes.append(
                "Em andamento, entre outras: " + ", ".join(abertos) + "."
            )

    return " ".join(partes)


def gerar_relatorio(config: dict) -> str:
    """Busca dados no TickTick e monta o relatório falado da semana."""
    cliente = Cliente(config)
    agora = datetime.now().astimezone()
    inicio = inicio_da_semana(agora)
    concluidas = cliente.tarefas_concluidas(inicio, agora)
    ativas = cliente.tarefas_ativas()
    return montar_relatorio_semana(
        concluidas,
        ativas,
        config.get("tratamento", "senhor"),
        agora=agora,
    )


def _parse_data_ticktick(valor: str | None) -> date | None:
    if not valor:
        return None
    # Exemplos: 2019-11-14T03:00:00+0000  ou  com milissegundos
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", valor)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def tarefas_de_hoje(tarefas: list[dict], hoje: date | None = None) -> list[dict]:
    hoje = hoje or date.today()
    resultado = []
    for t in tarefas:
        due = _parse_data_ticktick(t.get("dueDate") or t.get("startDate"))
        if due == hoje:
            resultado.append(t)
    return resultado


def tarefas_atrasadas(tarefas: list[dict], hoje: date | None = None) -> list[dict]:
    hoje = hoje or date.today()
    resultado = []
    for t in tarefas:
        due = _parse_data_ticktick(t.get("dueDate") or t.get("startDate"))
        if due is not None and due < hoje:
            resultado.append(t)
    return resultado


def falar_lista(tarefas: list[dict], tratamento: str, limite: int = 5) -> str:
    if not tarefas:
        return f"Nenhuma tarefa por aqui, {tratamento}."
    nomes = [t.get("title") or "sem título" for t in tarefas[:limite]]
    if len(tarefas) == 1:
        return f"Você tem uma tarefa: {nomes[0]}."
    if len(tarefas) <= limite:
        corpo = ", ".join(nomes[:-1]) + f" e {nomes[-1]}"
        return f"Você tem {len(tarefas)} tarefas: {corpo}."
    corpo = ", ".join(nomes)
    resto = len(tarefas) - limite
    return (
        f"Você tem {len(tarefas)} tarefas. As primeiras: {corpo}. "
        f"E mais {resto}."
    )


def falar_cobranca(tarefas: list[dict], tratamento: str, limite: int = 3) -> str:
    """Frase curta de cobrança periódica."""
    if not tarefas:
        return ""
    nomes = [t.get("title") or "sem título" for t in tarefas[:limite]]
    if len(tarefas) == 1:
        return f"{tratamento}, ainda falta: {nomes[0]}."
    if len(tarefas) <= limite:
        corpo = ", ".join(nomes[:-1]) + f" e {nomes[-1]}"
        return f"{tratamento}, ainda faltam: {corpo}."
    return (
        f"{tratamento}, você tem {len(tarefas)} tarefas pendentes. "
        f"Entre elas: {', '.join(nomes)}."
    )


def achar_tarefa(tarefas: list[dict], pedido: str) -> dict | None:
    """Encontra tarefa pelo título, tolerando 'já bebi' ≈ 'BEBER 3L…'."""
    alvo = normalizar(pedido)
    if not alvo:
        return None

    # Remove ruído de fala: "ja", "a", "o", "de"…
    ruido = {
        "ja", "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
        "pra", "para", "com", "no", "na", "me", "eu", "tarefa", "hoje",
    }
    palavras_alvo = [p for p in alvo.split() if p not in ruido and len(p) > 1]
    if not palavras_alvo:
        palavras_alvo = alvo.split()

    def raiz(p: str) -> str:
        return p[:4] if len(p) >= 4 else p

    raizes_alvo = {raiz(p) for p in palavras_alvo}

    # 1) título contém o pedido inteiro (ou o contrário)
    for t in tarefas:
        titulo = normalizar(t.get("title") or "")
        if not titulo:
            continue
        if alvo in titulo or titulo in alvo or titulo.startswith(alvo):
            return t

    # 2) sobreposição de palavras / raízes (bebi↔beber, agua↔agua)
    melhor = None
    melhor_nota = 0
    for t in tarefas:
        titulo = normalizar(t.get("title") or "")
        palavras_titulo = [p for p in titulo.split() if p not in ruido]
        raizes_titulo = {raiz(p) for p in palavras_titulo}
        nota = sum(1 for r in raizes_alvo if r in raizes_titulo)
        # bônus se quase todas as palavras do pedido bateram
        if palavras_alvo and nota == len(palavras_alvo):
            nota += 2
        if nota > melhor_nota:
            melhor_nota = nota
            melhor = t
    return melhor if melhor_nota > 0 else None
