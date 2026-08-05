"""Perfil da máquina: mede o que ela aguenta e ajusta o Jarvis a ela.

A ideia é o Jarvis rodar em qualquer PC sem configuração manual — numa máquina
fraca ele escolhe modelos leves, numa forte aproveita os pesados.

O que depende da máquina e o que não depende:

    Escuta (Whisper)   roda aqui  -> tamanho do modelo importa muito
    Voz offline (Piper) roda aqui -> só a CPU
    Clonagem (XTTS)    roda aqui  -> inviável sem CUDA
    Resposta (Claude)  roda na nuvem -> a máquina não muda a capacidade

O modelo do Claude entra no perfil por um motivo indireto, não por capacidade:
o que o usuário sente é a soma. Numa máquina em que a transcrição já leva três
segundos, um modelo de nuvem mais lento empurra a resposta para além dos oito;
numa máquina rápida, o mesmo modelo cabe folgado.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class Perfil:
    """Retrato do que a máquina aguenta."""

    nucleos: int
    ram_gb: float
    disco_livre_gb: float
    tem_cuda: bool
    gpu: str
    pontos_cpu: float  # operações por segundo, medido — não é frequência de catálogo
    nivel: str = ""
    motivos: list[str] = field(default_factory=list)


# Índice de velocidade POR NÚCLEO, normalizado para o Xeon E5-2660 v3 (2014,
# 2,6 GHz) valer 1,0. Um núcleo moderno de desktop fica entre 2,5 e 4.
#
# Mede um núcleo só de propósito: a transcrição é sensível à velocidade de cada
# núcleo, não à soma. Um teste com numpy daria "CPU rápida" nesta máquina —
# o BLAS espalha por 20 threads — enquanto o Whisper leva 3,2s.
CPU_FRACA = 0.75
CPU_FORTE = 2.2


def _ram_total_gb() -> float:
    """RAM total, sem depender de biblioteca externa."""
    if os.name != "nt":
        try:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
        except (ValueError, OSError):
            return 0.0

    class Status(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = Status()
    status.dwLength = ctypes.sizeof(Status)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullTotalPhys / 1024**3


def _gpu() -> tuple[bool, str]:
    """(tem CUDA, nome da placa). Só NVIDIA serve para os modelos locais."""
    if shutil.which("nvidia-smi"):
        try:
            saida = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            nome = saida.stdout.strip().splitlines()
            if nome:
                return True, nome[0].strip()
        except (OSError, subprocess.SubprocessError):
            pass

    if os.name == "nt":
        try:
            saida = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            linhas = [x.strip() for x in saida.stdout.splitlines()[1:] if x.strip()]
            if linhas:
                return False, linhas[0]
        except (OSError, subprocess.SubprocessError):
            pass

    return False, "desconhecida"


# Voltas por segundo do laço abaixo, medidas num Xeon E5-2660 v3 (2014,
# 2,6 GHz): 16.271.427. Serve de divisor para o índice valer 1,0 nele.
# Recalibre se mudar o corpo do laço — o número depende dele.
VOLTAS_DE_REFERENCIA = 16_270_000


def _uma_amostra(segundos: float) -> float:
    """Voltas por segundo de um laço aritmético em um único núcleo."""
    inicio = time.perf_counter()
    voltas = 0
    x = 0.0
    while True:
        for _ in range(20_000):
            x = x * 1.000001 + 1.0
        voltas += 20_000
        if time.perf_counter() - inicio >= segundos:
            break
    return voltas / (time.perf_counter() - inicio)


def _medir_cpu(amostras: int = 3) -> float:
    """Mede a velocidade de UM núcleo, que é o que a transcrição sente.

    Laço aritmético puro de propósito: nada de numpy, cujo BLAS distribui por
    todos os threads e mediria vazão total em vez de latência por núcleo.

    Pega a MELHOR de várias amostras. Uma medição só variou 66% entre duas
    execuções seguidas nesta máquina — jogo aberto, antivírus e escalonamento
    de frequência atrapalham, e todos só fazem o número cair. O melhor
    resultado é o mais próximo da capacidade real.
    """
    melhor = max(_uma_amostra(0.25) for _ in range(amostras))
    return round(melhor / VOLTAS_DE_REFERENCIA, 2)


def perfilar() -> Perfil:
    """Levanta o perfil da máquina. Leva menos de um segundo."""
    tem_cuda, gpu = _gpu()
    perfil = Perfil(
        nucleos=os.cpu_count() or 1,
        ram_gb=round(_ram_total_gb(), 1),
        disco_livre_gb=round(shutil.disk_usage(os.path.expanduser("~")).free / 1024**3, 1),
        tem_cuda=tem_cuda,
        gpu=gpu,
        pontos_cpu=_medir_cpu(),
    )

    motivos = []
    if perfil.pontos_cpu < CPU_FRACA:
        motivos.append(f"CPU lenta (índice {perfil.pontos_cpu})")
    elif perfil.pontos_cpu >= CPU_FORTE:
        motivos.append(f"CPU rápida (índice {perfil.pontos_cpu})")

    if perfil.ram_gb < 8:
        motivos.append(f"pouca RAM ({perfil.ram_gb:.0f} GB)")
    if perfil.nucleos < 4:
        motivos.append(f"poucos núcleos ({perfil.nucleos})")
    if tem_cuda:
        motivos.append(f"GPU NVIDIA ({gpu})")
    else:
        motivos.append("sem CUDA — modelos locais pesados ficam fora")

    fraca = perfil.pontos_cpu < CPU_FRACA or perfil.ram_gb < 8 or perfil.nucleos < 4
    forte = perfil.pontos_cpu >= CPU_FORTE and perfil.ram_gb >= 16 and tem_cuda

    perfil.nivel = "fraca" if fraca else ("forte" if forte else "média")
    perfil.motivos = motivos
    return perfil


def recomendar(perfil: Perfil) -> dict:
    """Configurações que cabem nesta máquina.

    Devolve só o que difere do padrão, para mesclar no `config.local.json`.
    """
    # A escada saiu de medição, não de intuição. No Xeon de referência
    # (índice 1,0) o `small` leva 3,1s para transcrever e o `base` 1,2s — 2,6x
    # de diferença, com a mesma qualidade em fala limpa. Abaixo de índice 2 o
    # `small` estoura o orçamento de latência de um assistente falado.
    if perfil.nivel == "fraca":
        ajustes = {
            "modelo_de_escuta": "base",
            "whisper_beam_size": 1,
            "modelo_de_conversa": "claude-haiku-4-5",  # compensa a CPU lenta
            "usar_frases_gravadas": True,
        }
    elif perfil.nivel == "forte":
        ajustes = {
            "modelo_de_escuta": "small",  # a CPU aguenta o mais preciso
            "whisper_beam_size": 5,
            "modelo_de_conversa": "claude-sonnet-5",
            "usar_frases_gravadas": True,
        }
    else:
        ajustes = {
            "modelo_de_escuta": "base",
            "whisper_beam_size": 1,
            "modelo_de_conversa": "claude-sonnet-5",
            "usar_frases_gravadas": True,
        }

    # A clonagem de voz só é viável com CUDA: medido em CPU, dá 3,9x o tempo
    # real, o que inviabiliza síntese ao vivo.
    ajustes["clonagem_ao_vivo_viavel"] = perfil.tem_cuda
    return ajustes


def sugestoes(perfil: Perfil) -> list[str]:
    """O que valeria melhorar nesta máquina, em ordem de impacto."""
    itens = []

    if not perfil.tem_cuda:
        itens.append(
            "Uma placa NVIDIA (uma RTX 3060 de 12 GB já basta) permitiria "
            "clonagem de voz ao vivo e transcrição bem mais rápida. É a "
            "melhoria de maior impacto aqui."
        )
    if perfil.pontos_cpu < CPU_FRACA:
        itens.append(
            "A CPU é o gargalo da transcrição. Enquanto não trocar, o modelo "
            "de escuta 'base' responde bem mais rápido que o 'small'."
        )
    if perfil.ram_gb < 15:
        itens.append(
            f"São {perfil.ram_gb:.1f} GB de RAM. Dobrar para 32 GB tira o "
            "sistema do disco quando há jogo e assistente abertos juntos."
        )
    if perfil.disco_livre_gb < 25:
        itens.append(
            f"Restam {perfil.disco_livre_gb:.1f} GB livres no disco — pouco. "
            "Só os modelos de voz e escuta já ocupam vários GB, e a clonagem "
            "levou mais de 3 GB."
        )
    if not itens:
        itens.append("Nada gritante: esta máquina dá conta de tudo que o Jarvis faz.")
    return itens
