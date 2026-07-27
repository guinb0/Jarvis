"""Registro dos comandos disponíveis.

Para ensinar um truque novo ao Jarvis: crie a subclasse de `Comando` em um
módulo aqui dentro e acrescente uma instância à lista `COMANDOS`. A ordem
importa — o primeiro comando que aceitar a frase é o que responde.
"""

from .base import Comando, PedidoDeEncerramento, normalizar
from .basicos import Ajuda, Data, Encerrar, Horas, Saudacao
from .sistema import AbrirPrograma, Bloquear, Pesquisar, Volume

COMANDOS: list[Comando] = [
    Saudacao(),
    Horas(),
    Data(),
    Volume(),
    Bloquear(),
    AbrirPrograma(),
    Pesquisar(),
    Ajuda(),
    Encerrar(),
]

__all__ = ["COMANDOS", "Comando", "PedidoDeEncerramento", "normalizar"]
