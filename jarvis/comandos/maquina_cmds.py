"""Comandos sobre a própria máquina: como ela está e o que melhorar."""

from __future__ import annotations

from .base import Comando


class Diagnostico(Comando):
    nome = "diagnóstico"
    descricao = "Conta como está o PC: processador, memória, disco e placa de vídeo."
    gatilhos = (
        "como esta o pc", "como esta o computador", "diagnostico",
        "configuracao da maquina", "specs", "config do pc",
        "como esta a maquina", "status do pc", "status da maquina",
    )

    def executar(self, frase: str, config: dict) -> str:
        from ..maquina import perfilar

        p = perfilar()
        # Sem .capitalize(): ele rebaixaria o resto do nome, e "Radeon RX 5500 XT"
        # viraria "Radeon rx 5500 xt".
        placa = p.gpu if p.gpu != "desconhecida" else "placa desconhecida"
        cuda = "com CUDA" if p.tem_cuda else "sem CUDA"

        return (
            f"Máquina de nível {p.nivel}, {config['tratamento']}. "
            f"{p.nucleos} núcleos com índice de velocidade {p.pontos_cpu:.1f}, "
            f"{p.ram_gb:.0f} gigas de memória e {p.disco_livre_gb:.0f} livres em disco. "
            f"Placa {placa}, {cuda}."
        )


class Melhorias(Comando):
    nome = "melhorias"
    descricao = "Sugere o que valeria melhorar nesta máquina."
    gatilhos = (
        "o que melhorar", "sugestoes de melhoria", "como melhorar o pc",
        "vale a pena trocar", "o que devo trocar", "upgrade",
        "como melhorar a maquina", "o que esta travando",
    )

    def executar(self, frase: str, config: dict) -> str:
        from ..maquina import perfilar, sugestoes

        itens = sugestoes(perfilar())
        # Fala só as duas primeiras: já vêm ordenadas por impacto, e uma lista
        # longa lida em voz alta não se retém.
        faladas = " ".join(itens[:2])
        resto = (
            f" Há mais {len(itens) - 2} pontos, se quiser ouvir."
            if len(itens) > 2
            else ""
        )
        return f"{faladas}{resto}"
