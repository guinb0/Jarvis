"""Abrir jogos instalados.

A lista não é fixa: o catálogo é lido do Steam e da Epic na primeira vez que o
comando roda, então jogos instalados depois passam a funcionar sozinhos, sem
mexer no código.

Jogos são sempre iniciados pela loja (`steam://`, `com.epicgames.launcher://`) e
não pelo .exe direto — é assim que a loja cuida da autenticação, da nuvem e das
atualizações. Chamar o executável na mão costuma falhar ou abrir a loja de
qualquer jeito.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from .base import Comando, normalizar

# Itens que o Steam guarda como "jogo" mas ninguém quer abrir.
_IGNORADOS = ("redistributables", "steam linux runtime", "proton", "steamvr")

# Abreviações que a gente fala mas que não estão no nome oficial. A chave é o
# que você diz; o valor é um trecho do nome registrado na loja.
APELIDOS = {
    "dbd": "dead by daylight",
    "cs": "counter-strike",
    "cs2": "counter-strike",
    "counter strike": "counter-strike",
    "pvz": "plants vs",
    "repo": "r.e.p.o",
    "among as": "among us",  # o Whisper erra esse com frequência
}


def _raiz_do_steam() -> Path | None:
    """Pasta de instalação do Steam, lida do registro do Windows."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as chave:
            return Path(winreg.QueryValueEx(chave, "SteamPath")[0])
    except OSError:
        return None


def _bibliotecas_do_steam(raiz: Path) -> list[Path]:
    """Todas as pastas `steamapps`, incluindo bibliotecas em outros discos."""
    bibliotecas = [raiz / "steamapps"]

    catalogo = raiz / "steamapps" / "libraryfolders.vdf"
    if catalogo.exists():
        texto = catalogo.read_text(encoding="utf-8", errors="replace")
        for caminho in re.findall(r'"path"\s+"([^"]+)"', texto):
            pasta = Path(caminho.replace("\\\\", "\\")) / "steamapps"
            if pasta not in bibliotecas:
                bibliotecas.append(pasta)

    return [b for b in bibliotecas if b.is_dir()]


def _jogos_do_steam() -> dict[str, str]:
    """Mapeia nome do jogo -> URI de lançamento, lendo os appmanifest do Steam."""
    raiz = _raiz_do_steam()
    if raiz is None:
        return {}

    encontrados: dict[str, str] = {}
    for biblioteca in _bibliotecas_do_steam(raiz):
        for manifesto in biblioteca.glob("appmanifest_*.acf"):
            texto = manifesto.read_text(encoding="utf-8", errors="replace")
            identificador = re.search(r'"appid"\s+"(\d+)"', texto)
            nome = re.search(r'"name"\s+"([^"]+)"', texto)
            if not (identificador and nome):
                continue
            if any(lixo in nome.group(1).lower() for lixo in _IGNORADOS):
                continue
            encontrados[nome.group(1)] = f"steam://rungameid/{identificador.group(1)}"

    return encontrados


def _jogos_da_epic() -> dict[str, str]:
    """Mesma ideia para a Epic, que guarda um .item JSON por item instalado."""
    pasta = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    pasta = pasta / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not pasta.is_dir():
        return {}

    encontrados: dict[str, str] = {}
    for manifesto in pasta.glob("*.item"):
        try:
            dados = json.loads(manifesto.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue

        # "games" separa o jogo de verdade dos pacotes de conteúdo extra.
        if "games" not in (dados.get("AppCategories") or []):
            continue

        nome, aplicativo = dados.get("DisplayName"), dados.get("AppName")
        if nome and aplicativo:
            encontrados[nome] = (
                f"com.epicgames.launcher://apps/{aplicativo}?action=launch&silent=true"
            )

    return encontrados


def _limpar(texto: str) -> str:
    """`normalizar` + espaços colapsados.

    Necessário porque `normalizar` troca cada símbolo por um espaço, e nomes como
    "Zombies™ Garden" viram "zombies  garden" — com dois espaços, o casamento
    exato contra a frase falada nunca aconteceria.
    """
    return " ".join(normalizar(texto).split())


@lru_cache(maxsize=1)
def catalogo() -> dict[str, tuple[str, str]]:
    """`{nome normalizado: (nome de exibição, URI)}` de tudo que está instalado."""
    bruto = {**_jogos_do_steam(), **_jogos_da_epic()}
    return {_limpar(nome): (nome, uri) for nome, uri in bruto.items()}


class AbrirJogo(Comando):
    nome = "jogo"
    descricao = "Abre um jogo instalado: 'abrir dead by daylight', 'jogar phasmophobia'."
    gatilhos = ("abrir", "abre", "abra", "inicia", "iniciar", "executa", "jogar", "joga")

    def _encontrar(self, frase: str) -> tuple[str, str] | None:
        """Casa a frase com um jogo instalado. O nome mais completo tem prioridade."""
        frase_normalizada = _limpar(frase)
        jogos = catalogo()

        # Um apelido falado vira o trecho oficial antes da comparação. O valor
        # também passa por `_limpar`, senão a pontuação do nome registrado
        # ("counter-strike", "r.e.p.o") nunca casaria com a frase.
        for apelido in sorted(APELIDOS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(_limpar(apelido))}\b", frase_normalizada):
                frase_normalizada += " " + _limpar(APELIDOS[apelido])

        chaves = sorted(jogos, key=len, reverse=True)

        # Primeira passada: nome completo. Garante que um casamento exato sempre
        # ganhe do prefixo de outro jogo.
        for chave in chaves:
            if chave in frase_normalizada:
                return jogos[chave]

        # Segunda passada: prefixos, do mais longo para o mais curto. É o que faz
        # "plants vs zombies" achar o jogo sem precisar recitar "garden warfare 2
        # deluxe edition", e "counter strike" achar o "counter strike 2".
        for chave in chaves:
            palavras = chave.split()
            for quantidade in range(len(palavras) - 1, 1, -1):
                inicio = " ".join(palavras[:quantidade])
                if len(inicio) >= 6 and inicio in frase_normalizada:
                    return jogos[chave]

        return None

    def aceita(self, frase: str) -> bool:
        # Exige o verbo E o nome do jogo, senão "o que é dead by daylight?"
        # abriria o jogo em vez de virar pergunta para o Claude.
        return super().aceita(frase) and self._encontrar(frase) is not None

    def executar(self, frase: str, config: dict) -> str:
        encontrado = self._encontrar(frase)
        if encontrado is None:
            instalados = ", ".join(sorted(nome for nome, _ in catalogo().values()))
            return f"Não achei esse jogo. Instalados: {instalados}."

        nome, uri = encontrado
        try:
            os.startfile(uri)  # noqa: S606 — URI de loja, não entrada do usuário
        except OSError as erro:
            return f"Não consegui abrir {nome}: {erro}"

        return f"Abrindo {nome}, {config['tratamento']}."
