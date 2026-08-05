"""Registro dos comandos disponíveis.

Para ensinar um truque novo ao Jarvis: crie a subclasse de `Comando` em um
módulo aqui dentro e acrescente uma instância à lista `COMANDOS`. A ordem
importa — o primeiro comando que aceitar a frase é o que responde.
"""

from .base import Comando, PedidoDeEncerramento, normalizar
from .basicos import Ajuda, Data, Encerrar, Horas, Saudacao
from .github_cmds import (
    IssuesGitHub,
    NotificacoesGitHub,
    ProjetosGitHub,
    PullRequestsGitHub,
    StatusGitHub,
)
from .jogos import AbrirJogo
from .maquina_cmds import Diagnostico, Melhorias
from .sistema import AbrirPrograma, Bloquear, Pesquisar, Volume
from .tarefas import ConcluirTarefa, CriarTarefa, ListarTarefas, RelatorioProdutividade

COMANDOS: list[Comando] = [
    Saudacao(),
    Horas(),
    Data(),
    Volume(),
    Bloquear(),
    Diagnostico(),
    Melhorias(),
    RelatorioProdutividade(),
    ListarTarefas(),
    ConcluirTarefa(),
    CriarTarefa(),
    NotificacoesGitHub(),
    ProjetosGitHub(),
    PullRequestsGitHub(),
    IssuesGitHub(),
    StatusGitHub(),
    # Antes de AbrirPrograma: os dois usam "abrir", e só este conhece os jogos.
    AbrirJogo(),
    AbrirPrograma(),
    Pesquisar(),
    Ajuda(),
    Encerrar(),
]

__all__ = ["COMANDOS", "Comando", "PedidoDeEncerramento", "normalizar"]
