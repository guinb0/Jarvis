"""Gatilho de teclado: acorda o Jarvis só quando você chama.

Enquanto dorme, o microfone nem é aberto — ele não escuta, não transcreve e
não responde a nada. Só depois da sequência de teclas ele grava uma fala,
responde e volta a dormir.

A captura é global (funciona com o jogo em primeiro plano) e usa o mesmo
mecanismo do Windows que o push-to-talk do Discord.
"""

from __future__ import annotations

import sys
import threading
import time
from collections import deque


class Gatilho:
    """Espera uma tecla ser apertada N vezes seguidas."""

    def __init__(self, tecla: str, vezes: int, intervalo: float):
        from pynput import keyboard  # importado aqui para o erro vir cedo e claro

        self.tecla = tecla
        self.vezes = vezes
        self.intervalo = intervalo

        self._acordou = threading.Event()
        self._toques: deque[float] = deque(maxlen=vezes)
        self._alvo = self._resolver_tecla(keyboard, tecla)

        self._ouvinte = keyboard.Listener(on_press=self._ao_apertar)
        self._ouvinte.daemon = True
        self._ouvinte.start()

    @staticmethod
    def _resolver_tecla(keyboard, nome: str):
        """Converte 'delete' / 'f8' / 'a' no objeto de tecla do pynput."""
        especial = getattr(keyboard.Key, nome.lower(), None)
        if especial is not None:
            return especial
        if len(nome) == 1:
            return keyboard.KeyCode.from_char(nome.lower())
        raise ValueError(
            f"Tecla '{nome}' não reconhecida. Use um nome do pynput "
            "(delete, insert, f8, pause, scroll_lock...) ou um único caractere."
        )

    def _mesma_tecla(self, tecla) -> bool:
        from pynput import keyboard

        if tecla == self._alvo:
            return True
        # Teclas de caractere chegam como KeyCode; compara pelo char para não
        # depender de maiúscula/minúscula nem do estado do Shift.
        alvo_char = getattr(self._alvo, "char", None)
        return (
            alvo_char is not None
            and isinstance(tecla, keyboard.KeyCode)
            and tecla.char is not None
            and tecla.char.lower() == alvo_char
        )

    def _ao_apertar(self, tecla) -> None:
        if not self._mesma_tecla(tecla):
            self._toques.clear()  # outra tecla no meio quebra a sequência
            return

        agora = time.monotonic()
        self._toques.append(agora)

        if len(self._toques) == self.vezes and agora - self._toques[0] <= self.intervalo:
            self._toques.clear()
            self._acordou.set()

    @property
    def descricao(self) -> str:
        return f"{self.tecla.upper()} {self.vezes}x"

    def esperar(self) -> None:
        """Bloqueia até a sequência ser digitada.

        A espera é fatiada em vez de infinita porque no Windows um
        `Event.wait()` sem prazo engole o Ctrl+C.
        """
        while not self._acordou.wait(timeout=0.3):
            pass
        self._acordou.clear()

    def disparou(self) -> bool:
        """Diz se a sequência foi digitada, sem bloquear, e consome o aviso.

        É o que permite desligar no meio de uma escuta: sem isto, apertar a
        tecla enquanto ele espera você falar não teria efeito nenhum até você
        falar alguma coisa.
        """
        if self._acordou.is_set():
            self._acordou.clear()
            return True
        return False

    @staticmethod
    def bipar(ativando: bool) -> None:
        """Bipe de reserva, para quando não há voz: agudo liga, grave desliga."""
        try:
            import winsound

            winsound.Beep(880 if ativando else 440, 120)
        except (ImportError, RuntimeError):
            pass  # sem alto-falante de sistema; o aviso na tela já basta

    def parar(self) -> None:
        self._ouvinte.stop()


def carregar_gatilho(config: dict) -> Gatilho | None:
    """Cria o gatilho, ou devolve None se estiver desligado / indisponível."""
    if not config["ativar_por_tecla"]:
        return None

    try:
        return Gatilho(
            tecla=config["tecla_de_ativacao"],
            vezes=config["toques_para_ativar"],
            intervalo=config["intervalo_entre_toques"],
        )
    except ImportError:
        print(
            "[gatilho] falta o pynput. Rode: pip install -r requirements.txt\n"
            "Sem ele o Jarvis responde a tudo que ouvir.",
            file=sys.stderr,
        )
    except ValueError as erro:
        print(f"[gatilho] {erro}", file=sys.stderr)
    return None
