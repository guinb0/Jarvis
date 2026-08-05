"""Cobra tarefas e emite o relatório semanal de produtividade."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from datetime import datetime

from . import ticktick
from .configuracoes import carregar


class Cobrador:
    """Thread que lembra pendências e, no dia certo, fala o relatório da semana."""

    def __init__(
        self,
        config: dict,
        voz,
        *,
        esta_acordado: Callable[[], bool] | None = None,
    ):
        self.config = config
        self.voz = voz
        self.esta_acordado = esta_acordado or (lambda: True)
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        minutos = float(config.get("ticktick_cobrar_minutos", 60))
        self.intervalo = max(60.0, minutos * 60.0)
        self.cobrar_dormindo = bool(config.get("ticktick_cobrar_dormindo", True))
        # Última data (YYYY-MM-DD) em que o relatório semanal automático saiu.
        self._ultimo_relatorio_dia: str | None = None

    def iniciar(self) -> None:
        tem_token = bool(self.config.get("ticktick_access_token"))
        cobrar = bool(self.config.get("ticktick_cobrar", True))
        relatorio = bool(self.config.get("ticktick_relatorio_automatico", True))
        if not tem_token:
            print("[cobrador] TickTick sem token — cobrança desligada.", file=sys.stderr)
            return
        if not cobrar and not relatorio:
            return
        self._thread = threading.Thread(
            target=self._loop, name="cobrador-ticktick", daemon=True
        )
        self._thread.start()
        partes = []
        if cobrar:
            onde = "também dormindo" if self.cobrar_dormindo else "só acordado"
            partes.append(f"cobrança a cada {self.intervalo / 60:.0f} min ({onde})")
        if relatorio:
            dia = int(self.config.get("ticktick_relatorio_dia", 6))  # 6 = domingo
            hora = int(self.config.get("ticktick_relatorio_hora", 20))
            nomes = (
                "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"
            )
            partes.append(f"relatório semanal {nomes[dia]} às {hora}h")
        print("[cobrador] " + "; ".join(partes), file=sys.stderr)

    def parar(self) -> None:
        self._parar.set()

    def _loop(self) -> None:
        if self._parar.wait(min(self.intervalo, 5 * 60)):
            return
        while not self._parar.is_set():
            try:
                self.config = carregar()
                self._talvez_relatorio()
                if self.config.get("ticktick_cobrar", True):
                    self._cobrar()
            except Exception as erro:  # noqa: BLE001
                print(f"[cobrador] {erro}", file=sys.stderr)
            if self._parar.wait(self.intervalo):
                return

    def _falar(self, texto: str) -> None:
        print(f"Jarvis: {texto}")
        if self.voz:
            try:
                self.voz.falar(texto)
            except Exception as erro:
                print(f"[cobrador] voz falhou: {erro}", file=sys.stderr)

    def _talvez_relatorio(self) -> None:
        if not self.config.get("ticktick_relatorio_automatico", True):
            return
        if not self.cobrar_dormindo and not self.esta_acordado():
            return

        agora = datetime.now().astimezone()
        dia_cfg = int(self.config.get("ticktick_relatorio_dia", 6))
        hora_cfg = int(self.config.get("ticktick_relatorio_hora", 20))
        if agora.weekday() != dia_cfg or agora.hour < hora_cfg:
            return

        chave = agora.strftime("%Y-%m-%d")
        if self._ultimo_relatorio_dia == chave:
            return

        try:
            texto = ticktick.gerar_relatorio(self.config)
        except ticktick.TickTickErro as erro:
            print(f"[cobrador] relatório: {erro}", file=sys.stderr)
            return

        self._ultimo_relatorio_dia = chave
        self._falar(texto)

    def _cobrar(self) -> None:
        if not self.cobrar_dormindo and not self.esta_acordado():
            return

        try:
            cliente = ticktick.Cliente(self.config)
            todas = cliente.tarefas_ativas()
        except ticktick.TickTickErro as erro:
            print(f"[cobrador] {erro}", file=sys.stderr)
            return

        atrasadas = ticktick.tarefas_atrasadas(todas)
        hoje = ticktick.tarefas_de_hoje(todas)
        prioridade = atrasadas + [t for t in hoje if t not in atrasadas]
        lista = prioridade or todas
        if not lista:
            return

        texto = ticktick.falar_cobranca(lista, self.config.get("tratamento", "senhor"))
        if texto:
            self._falar(texto)
