"""Autoriza o Jarvis a usar sua conta TickTick (OAuth no navegador).

No painel https://developer.ticktick.com/manage , edite o app e coloque:

    OAuth redirect URL = http://127.0.0.1:8765/callback

Jeito mais simples (2 passos):

    python scripts/autorizar_ticktick.py --url
    # abra a URL, clique Allow, copie a barra de endereço (mesmo se a página falhar)
    python scripts/autorizar_ticktick.py --code "COLE_A_URL_OU_O_CODE_AQUI"
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from jarvis.configuracoes import carregar
from jarvis import ticktick


def _credenciais() -> tuple[str, str]:
    config = carregar()
    local = ticktick._carregar_local()
    client_id = local.get("ticktick_client_id") or config.get("ticktick_client_id", "")
    client_secret = (
        local.get("ticktick_client_secret") or config.get("ticktick_client_secret", "")
    )
    if not client_id or not client_secret:
        raise SystemExit(
            "Faltam ticktick_client_id / ticktick_client_secret no config.local.json"
        )
    return client_id, client_secret


def _extrair_code(texto: str) -> str:
    texto = texto.strip().strip('"').strip("'")
    if "code=" in texto:
        query = parse_qs(urlparse(texto).query)
        if query.get("code"):
            return query["code"][0]
    if texto and "://" not in texto:
        return texto
    raise SystemExit(
        "Não achei o code. Cole a URL completa "
        "(http://127.0.0.1:8765/callback?code=...) ou só o code."
    )


def _finalizar(client_id: str, client_secret: str, code: str) -> int:
    try:
        ticktick.trocar_codigo_por_token(client_id, client_secret, code)
    except ticktick.TickTickErro as erro:
        print(erro, file=sys.stderr)
        return 1

    print("Token salvo em config.local.json.")
    try:
        cliente = ticktick.Cliente()
        tarefas = cliente.tarefas_ativas()
        print(f"Conectado. {len(tarefas)} tarefa(s) ativa(s).")
    except ticktick.TickTickErro as erro:
        print(f"Token ok, mas a listagem falhou: {erro}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    analisador = argparse.ArgumentParser(description="Autoriza o TickTick no Jarvis.")
    analisador.add_argument(
        "--url",
        action="store_true",
        help="só mostra/abre a URL de autorização",
    )
    analisador.add_argument(
        "--code",
        metavar="CODE_OU_URL",
        help="code do OAuth ou URL completa do callback",
    )
    analisador.add_argument(
        "--esperar",
        action="store_true",
        help="sobe o servidor local e espera o redirect (modo antigo)",
    )
    args = analisador.parse_args()

    client_id, client_secret = _credenciais()

    if args.code:
        return _finalizar(client_id, client_secret, _extrair_code(args.code))

    url = ticktick.url_de_autorizacao(client_id)
    print("Abra esta URL, faça login se pedir e clique em Allow:")
    print()
    print(url)
    print()
    print("Depois copie a barra de endereço (mesmo se der erro de conexão) e rode:")
    print('  python scripts/autorizar_ticktick.py --code "COLE_A_URL_AQUI"')
    webbrowser.open(url)

    if args.url or not args.esperar:
        return 0

    # Modo opcional: espera o callback automaticamente.
    print()
    print(f"Esperando redirect em {ticktick.REDIRECT_URI} ...")
    codigo: dict[str, str | None] = {"code": None, "erro": None}
    pronto = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            caminho = urlparse(self.path).path
            if caminho != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(urlparse(self.path).query)
            if query.get("code"):
                codigo["code"] = query["code"][0]
                corpo = b"<html><body><h1>Jarvis autorizado. Pode fechar.</h1></body></html>"
                self.send_response(200)
            else:
                codigo["erro"] = query.get("error", ["sem code"])[0]
                corpo = b"<html><body><h1>Falha na autorizacao.</h1></body></html>"
                self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            pronto.set()

        def log_message(self, fmt, *args):
            return

    servidor = HTTPServer(("127.0.0.1", 8765), Handler)

    def servir() -> None:
        while not pronto.is_set():
            servidor.handle_request()

    threading.Thread(target=servir, daemon=True).start()
    if not pronto.wait(timeout=300):
        print("Tempo esgotado.", file=sys.stderr)
        return 1
    if not codigo["code"]:
        print(f"Autorização recusada: {codigo['erro']}", file=sys.stderr)
        return 1
    return _finalizar(client_id, client_secret, codigo["code"])


if __name__ == "__main__":
    raise SystemExit(main())
