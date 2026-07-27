"""Ponto de entrada do Jarvis.

    python -m jarvis                 # conversa por texto, respondendo em voz
    python -m jarvis --mudo          # só texto, sem tocar áudio
    python -m jarvis --dizer "oi"    # responde uma única frase e sai
"""

from __future__ import annotations

import argparse
import sys

from .cerebro import Cerebro
from .comandos import PedidoDeEncerramento
from .configuracoes import carregar


def carregar_voz(mudo: bool):
    """Devolve a voz carregada, ou None se estiver mudo / sem modelo baixado."""
    if mudo:
        return None

    try:
        from .voz import Voz

        return Voz()
    except FileNotFoundError as erro:
        print(f"[voz desativada] {erro}\n", file=sys.stderr)
    except ImportError:
        print(
            "[voz desativada] dependências ausentes. Rode: pip install -r requirements.txt\n",
            file=sys.stderr,
        )
    return None


def responder(cerebro: Cerebro, voz, frase: str) -> None:
    resposta = cerebro.responder(frase)
    print(f"Jarvis: {resposta}")
    if voz:
        voz.falar(resposta)


def main() -> int:
    analisador = argparse.ArgumentParser(prog="jarvis", description="Assistente pessoal.")
    analisador.add_argument("--mudo", action="store_true", help="não reproduzir áudio")
    analisador.add_argument("--dizer", metavar="FRASE", help="responder uma frase e sair")
    argumentos = analisador.parse_args()

    config = carregar()
    cerebro = Cerebro()
    voz = carregar_voz(argumentos.mudo)

    if argumentos.dizer:
        try:
            responder(cerebro, voz, argumentos.dizer)
        except PedidoDeEncerramento as despedida:
            print(f"Jarvis: {despedida}")
        return 0

    if config["falar_ao_iniciar"]:
        abertura = f"Sistemas online, {config['tratamento']}."
        print(f"Jarvis: {abertura}")
        if voz:
            voz.falar(abertura)

    print("(digite 'ajuda' para ver os comandos, 'sair' para encerrar)\n")

    while True:
        try:
            frase = input("Você: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        try:
            responder(cerebro, voz, frase)
        except PedidoDeEncerramento as despedida:
            print(f"Jarvis: {despedida}")
            if voz:
                voz.falar(str(despedida))
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
