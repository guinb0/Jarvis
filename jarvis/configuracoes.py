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

# Vozes do Piper em português, conforme o catálogo rhasspy/piper-voices.
VOZES_EM_PORTUGUES = {
    "pt_BR-faber-medium": "brasileira, masculina, grave",
    "pt_BR-cadu-medium": "brasileira, masculina",
    "pt_BR-jeff-medium": "brasileira, masculina",
    "pt_BR-edresson-low": "brasileira, masculina, modelo leve",
    "pt_PT-tugão-medium": "de Portugal, masculina",
}

# Voz padrão: masculina, português brasileiro.
VOZ_PADRAO = "pt_BR-faber-medium"

# Como o usuário é tratado nas respostas.
TRATAMENTO = "senhor"

# Nome usado para acordar o assistente por voz.
PALAVRA_DE_ATIVACAO = "jarvis"

# Modelo do Whisper usado para escutar. "small" acerta bem o português sem
# pesar demais; "medium" é mais preciso e bem mais lento; "base" é o inverso.
MODELO_DE_ESCUTA = "small"

_PADROES = {
    "voz": VOZ_PADRAO,
    "tratamento": TRATAMENTO,
    "palavra_de_ativacao": PALAVRA_DE_ATIVACAO,
    "falar_ao_iniciar": True,
    "modelo_de_escuta": MODELO_DE_ESCUTA,
    # Energia (RMS) acima da qual o bloco de áudio conta como fala. Suba se o
    # ambiente for barulhento e o Jarvis gravar sozinho; desça se ele não ouvir.
    "limiar_de_silencio": 0.015,
    # Segundos de silêncio que encerram a gravação de uma fala.
    "silencio_para_encerrar": 1.0,
    # Teto de segurança para uma única fala.
    "duracao_maxima_da_fala": 15.0,
    # Exigir "Jarvis" no início da frase no modo de voz.
    "exigir_palavra_de_ativacao": False,
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
