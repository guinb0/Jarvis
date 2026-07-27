"""Configurações centrais do Jarvis.

Os valores podem ser sobrescritos por um arquivo `config.local.json` na raiz do
projeto (ignorado pelo git), útil para ajustes que não devem ir para o
repositório.
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_MODELOS = RAIZ / "modelos"

# Voz padrão: masculina, português brasileiro.
# Alternativas: "pt_PT-tugao-medium" (Portugal), "pt_BR-edresson-low".
VOZ_PADRAO = "pt_BR-faber-medium"

# Como o usuário é tratado nas respostas.
TRATAMENTO = "senhor"

# Nome usado para acordar o assistente por voz.
PALAVRA_DE_ATIVACAO = "jarvis"

_PADROES = {
    "voz": VOZ_PADRAO,
    "tratamento": TRATAMENTO,
    "palavra_de_ativacao": PALAVRA_DE_ATIVACAO,
    "falar_ao_iniciar": True,
}


def carregar() -> dict:
    """Devolve as configurações, mesclando os padrões com `config.local.json`."""
    config = dict(_PADROES)
    local = RAIZ / "config.local.json"
    if local.exists():
        config.update(json.loads(local.read_text(encoding="utf-8")))
    return config


def caminho_do_modelo(nome_da_voz: str) -> Path:
    """Caminho do arquivo .onnx de uma voz dentro de `modelos/`."""
    return PASTA_MODELOS / f"{nome_da_voz}.onnx"
