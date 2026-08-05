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

# Frases fixas gravadas de antemão com a voz clonada do JARVIS. Ver
# scripts/gerar_frases_jarvis.py.
PASTA_FRASES = RAIZ / "frases-jarvis"

# Textos pessoais indexados via Postgres + pgvector. Ver jarvis/memoria.py.
# (A pasta memoria/ só guarda sementes opcionais para a 1ª carga.)
PASTA_MEMORIA = RAIZ / "memoria"

# Motor de síntese padrão.
#   "edge"  — vozes neurais, naturais; o texto da resposta vai para a Microsoft.
#   "piper" — roda na máquina, sem internet, mas soa bem mais robótico.
# Com "edge", o Piper entra sozinho como reserva se a internet cair.
MOTOR_PADRAO = "edge"

# Vozes neurais do Edge TTS. São as únicas cinco em português no catálogo.
VOZES_EDGE = {
    "pt-BR-ThalitaMultilingualNeural": "brasileira, feminina, a mais natural",
    "pt-BR-FranciscaNeural": "brasileira, feminina",
    "pt-BR-AntonioNeural": "brasileira, masculina",
    "pt-PT-RaquelNeural": "de Portugal, feminina",
    "pt-PT-DuarteNeural": "de Portugal, masculina",
}

VOZ_EDGE_PADRAO = "pt-BR-ThalitaMultilingualNeural"

# Vozes do Piper em português, conforme o catálogo rhasspy/piper-voices.
# Todas masculinas — o Piper não tem voz feminina em português.
VOZES_PIPER = {
    "pt_BR-faber-medium": "brasileira, masculina, grave",
    "pt_BR-cadu-medium": "brasileira, masculina",
    "pt_BR-jeff-medium": "brasileira, masculina",
    "pt_BR-edresson-low": "brasileira, masculina, modelo leve",
    "pt_PT-tugão-medium": "de Portugal, masculina",
}

VOZ_PIPER_PADRAO = "pt_BR-faber-medium"

# Como o usuário é tratado nas respostas.
TRATAMENTO = "senhor"

# Nome usado para acordar o assistente por voz.
PALAVRA_DE_ATIVACAO = "jarvis"

# Modelo do Whisper usado para escutar. "small" acerta bem o português sem
# pesar demais; "medium" é mais preciso e bem mais lento; "base" é o inverso.
MODELO_DE_ESCUTA = "small"

_PADROES = {
    "motor": MOTOR_PADRAO,
    "voz_edge": VOZ_EDGE_PADRAO,
    "voz_piper": VOZ_PIPER_PADRAO,
    "tratamento": TRATAMENTO,
    "palavra_de_ativacao": PALAVRA_DE_ATIVACAO,
    "falar_ao_iniciar": True,
    "modelo_de_escuta": MODELO_DE_ESCUTA,
    # beam_size do Whisper. 1 = rápido (bom em CPU); 5 = um pouco mais preciso.
    "whisper_beam_size": 1,
    # Energia (RMS) acima da qual o bloco de áudio conta como fala. Suba se o
    # ambiente for barulhento e o Jarvis gravar sozinho; desça se ele não ouvir.
    "limiar_de_silencio": 0.015,
    # Segundos de silêncio que encerram a gravação de uma fala. Entra direto na
    # latência: é espera morta depois que você já parou de falar. Abaixo de 0,5
    # ele começa a cortar quem pausa para pensar no meio da frase.
    "silencio_para_encerrar": 0.6,
    # Teto de segurança para uma única fala.
    "duracao_maxima_da_fala": 15.0,
    # Exigir "Jarvis" no início da frase no modo de voz.
    "exigir_palavra_de_ativacao": False,
    # Dormir até uma tecla ser apertada. Enquanto dorme o microfone nem é
    # aberto — nada é escutado, transcrito ou respondido.
    "ativar_por_tecla": True,
    "tecla_de_ativacao": "delete",
    "toques_para_ativar": 3,
    # Segundos para completar a sequência de toques.
    "intervalo_entre_toques": 1.5,
    # Confirmar em voz alta quando acorda e quando volta a dormir. Sem voz
    # disponível (--mudo, sem internet), vira um bipe: agudo ao ativar, grave
    # ao desativar.
    "avisar_ativacao": True,
    "aviso_ao_ativar": "Sistema ativado.",
    "aviso_ao_desativar": "Sistema desativado.",
    # Usar as frases gravadas com a voz clonada do JARVIS nas respostas fixas.
    # O que muda a cada vez (respostas do Claude, horas, buscas) continua
    # saindo pela voz do motor escolhido.
    "usar_frases_gravadas": True,
    # Deixar o Claude pesquisar na internet quando a resposta depender de
    # informação atual. Cobrado à parte: ~US$ 10 por mil buscas.
    "buscar_na_web": True,
    # Quantas páginas consultadas abrir no navegador depois de responder, para
    # você poder conferir a fonte. 0 desliga. Atrapalha com jogo em tela cheia.
    "abrir_fontes_no_navegador": 2,
    # Haiku só em conversa fiada/confirmação; Sonnet no resto (número, fato,
    # busca). Na dúvida, Sonnet. Desligue para mandar tudo ao Sonnet.
    "usar_roteador_leve": True,
    # Memória vetorial em SQLite: um arquivo, sem servidor e sem Docker.
    "usar_memoria": True,
    "memoria_resultados": 3,
    "memoria_limiar": 0.25,
    # Vazio = modelos/memoria.db.
    "memoria_banco": "",
    # TickTick — preencha no config.local.json e rode scripts/autorizar_ticktick.py
    "ticktick_client_id": "",
    "ticktick_client_secret": "",
    "ticktick_access_token": "",
    "ticktick_refresh_token": "",
    # Cobrar tarefas pendentes em voz alta de tempos em tempos.
    "ticktick_cobrar": True,
    "ticktick_cobrar_minutos": 60,
    # True = cobra mesmo com o Jarvis dormindo (DELETE).
    "ticktick_cobrar_dormindo": True,
    # Relatório semanal automático de produtividade (concluídas + pendentes).
    "ticktick_relatorio_automatico": True,
    # 0=segunda … 6=domingo. Hora local (0–23).
    "ticktick_relatorio_dia": 6,
    "ticktick_relatorio_hora": 20,
    # GitHub — Personal Access Token classic em config.local.json
    # Escopos: notifications, repo (ou public_repo)
    "github_token": "",
    # Espelha a lista de repos na tabela memorias (pgvector).
    "github_sincronizar_projetos": True,
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
