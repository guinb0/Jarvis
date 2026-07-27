"""Comandos que agem sobre o computador: abrir programas, volume, busca."""

from __future__ import annotations

import ctypes
import re
import subprocess
import webbrowser

from .base import Comando, normalizar

# Programas que o Jarvis sabe abrir. A chave é o que você fala; o valor é o
# executável. Nomes sem caminho são resolvidos pelo PATH do Windows.
PROGRAMAS = {
    "navegador": "https://www.google.com",
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "bloco de notas": "notepad.exe",
    "calculadora": "calc.exe",
    "explorador": "explorer.exe",
    "arquivos": "explorer.exe",
    "terminal": "wt.exe",
    "prompt": "cmd.exe",
    "gerenciador de tarefas": "taskmgr.exe",
    "configuracoes": "ms-settings:",
    "paint": "mspaint.exe",
}

# Teclas de mídia do Windows, acionadas via keybd_event.
VOLUME_MUDO = 0xAD
VOLUME_ABAIXAR = 0xAE
VOLUME_AUMENTAR = 0xAF
TECLA_SOLTA = 0x0002


def apertar_tecla(codigo: int, vezes: int = 1) -> None:
    """Simula o pressionar de uma tecla de mídia."""
    for _ in range(vezes):
        ctypes.windll.user32.keybd_event(codigo, 0, 0, 0)
        ctypes.windll.user32.keybd_event(codigo, 0, TECLA_SOLTA, 0)


class AbrirPrograma(Comando):
    nome = "abrir"
    descricao = "Abre um programa ou site: 'abrir a calculadora', 'abrir o youtube'."
    gatilhos = ("abrir", "abre", "abra", "inicia", "executa")

    def executar(self, frase: str, config: dict) -> str:
        frase_normalizada = normalizar(frase)

        # O nome mais longo ganha, para "gerenciador de tarefas" não virar "tarefas".
        for apelido in sorted(PROGRAMAS, key=len, reverse=True):
            if normalizar(apelido) in frase_normalizada:
                alvo = PROGRAMAS[apelido]
                try:
                    if alvo.startswith("http"):
                        webbrowser.open(alvo)
                    else:
                        subprocess.Popen(alvo, shell=True)
                except OSError as erro:
                    return f"Não consegui abrir {apelido}: {erro}"
                return f"Abrindo {apelido}, {config['tratamento']}."

        conhecidos = ", ".join(sorted(PROGRAMAS))
        return f"Não sei abrir isso. Eu conheço: {conhecidos}."


class Pesquisar(Comando):
    nome = "pesquisar"
    descricao = "Busca no Google: 'pesquisar por receita de bolo'."
    gatilhos = ("pesquisar", "pesquise", "procurar por", "busca por", "buscar por")

    def executar(self, frase: str, config: dict) -> str:
        # Tudo que vem depois do gatilho é o termo da busca.
        termo = re.sub(
            r"^.*?\b(pesquisar|pesquise|procurar|busca|buscar)\b\s*(por|sobre)?\s*",
            "",
            frase.strip(),
            flags=re.IGNORECASE,
        ).strip()

        if not termo:
            return f"O que devo pesquisar, {config['tratamento']}?"

        webbrowser.open(f"https://www.google.com/search?q={termo.replace(' ', '+')}")
        return f"Pesquisando por {termo}."


class Volume(Comando):
    nome = "volume"
    descricao = "Controla o som: 'aumentar o volume', 'abaixar o volume', 'mudo'."
    gatilhos = (
        "aumentar o volume", "aumenta o volume", "aumentar volume", "sobe o som",
        "abaixar o volume", "abaixa o volume", "diminuir o volume", "baixa o som",
        "mudo", "sem som", "silencio",
    )

    def executar(self, frase: str, config: dict) -> str:
        frase_normalizada = normalizar(frase)

        if any(p in frase_normalizada for p in ("mudo", "sem som", "silencio")):
            apertar_tecla(VOLUME_MUDO)
            return "Som cortado."

        # Cada toque move o volume 2%; 5 toques dão um passo perceptível.
        if any(p in frase_normalizada for p in ("aumentar", "aumenta", "sobe")):
            apertar_tecla(VOLUME_AUMENTAR, vezes=5)
            return "Volume aumentado."

        apertar_tecla(VOLUME_ABAIXAR, vezes=5)
        return "Volume reduzido."


class Bloquear(Comando):
    nome = "bloquear"
    descricao = "Bloqueia a sessão do Windows."
    gatilhos = ("bloquear o computador", "bloquear a tela", "trancar o computador")

    def executar(self, frase: str, config: dict) -> str:
        ctypes.windll.user32.LockWorkStation()
        return f"Bloqueando, {config['tratamento']}."
