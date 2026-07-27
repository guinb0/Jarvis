"""Conversa aberta com o Claude, para quando nenhum comando local responde.

É opcional: sem credencial da Anthropic o Jarvis segue funcionando só com os
comandos offline. A credencial vem da variável de ambiente ANTHROPIC_API_KEY
ou de um perfil criado com `ant auth login` — nenhuma chave fica no código.
"""

from __future__ import annotations

import sys

MODELO = "claude-opus-5"

# O Jarvis fala as respostas em voz alta, então elas precisam ser curtas:
# um parágrafo falado já é longo demais.
INSTRUCOES = """Você é o Jarvis, o assistente pessoal do usuário, e responde sempre em \
português brasileiro.

Suas respostas são convertidas em fala, então:
- Responda em no máximo duas ou três frases.
- Escreva números, datas e unidades por extenso quando forem curtos.
- Nada de listas, marcadores, tabelas, emoji ou formatação — só texto corrido.
- Sem preâmbulo. Responda direto ao que foi perguntado.

Trate o usuário por "{tratamento}". Seja direto e cordial, sem bajulação. \
Se não souber algo, diga isso em uma frase em vez de inventar."""


class SemCredencial(Exception):
    """Não há credencial da Anthropic configurada nesta máquina."""


def disponivel() -> bool:
    """Diz se a biblioteca da Anthropic está instalada."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


class Conversa:
    """Mantém o histórico do papo e consulta o modelo quando preciso."""

    def __init__(self, config: dict, limite_de_turnos: int = 12):
        import anthropic

        self.anthropic = anthropic
        self.cliente = anthropic.Anthropic()

        # O cliente é construído mesmo sem credencial e só falha na primeira
        # chamada. `auth_headers` fica vazio quando nenhuma das formas de
        # autenticação (chave, token ou perfil do `ant`) foi resolvida.
        if not self.cliente.auth_headers:
            raise SemCredencial("nenhuma credencial da Anthropic configurada")

        self.instrucoes = INSTRUCOES.format(tratamento=config["tratamento"])
        self.limite_de_turnos = limite_de_turnos
        self.historico: list[dict] = []

    def _chamar(self, mensagens: list[dict]):
        """Faz a chamada com desvio automático para outro modelo em recusas."""
        comum = dict(
            model=MODELO,
            max_tokens=2048,  # cobre o raciocínio e a resposta, que é curta
            system=self.instrucoes,
            messages=mensagens,
            # Raciocínio leve: o modelo pensa só o necessário e responde rápido.
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
        )

        try:
            return self.cliente.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                **comum,
            )
        except self.anthropic.BadRequestError:
            # Conta sem acesso ao desvio automático: segue sem ele.
            return self.cliente.messages.create(**comum)

    def responder(self, frase: str) -> str:
        mensagens = self.historico + [{"role": "user", "content": frase}]

        try:
            resposta = self._chamar(mensagens)
        except self.anthropic.AuthenticationError:
            return "Não estou conectado à nuvem: falta configurar a credencial da Anthropic."
        except self.anthropic.RateLimitError:
            return "Estou recebendo pedidos demais. Tente de novo em instantes."
        except self.anthropic.APIConnectionError:
            return "Não consegui acessar a internet agora."
        except self.anthropic.APIStatusError as erro:
            print(f"[conversa] erro {erro.status_code}: {erro.message}", file=sys.stderr)
            return "Deu problema ao consultar a nuvem."

        # Os filtros de segurança podem recusar o pedido: nesse caso o conteúdo
        # vem vazio, então é preciso checar antes de ler os blocos.
        if resposta.stop_reason == "refusal":
            return "Prefiro não responder isso."

        texto = " ".join(
            bloco.text.strip() for bloco in resposta.content if bloco.type == "text"
        ).strip()

        if not texto:
            return "Não consegui formular uma resposta."

        self.historico = mensagens + [{"role": "assistant", "content": texto}]
        # Mantém a memória curta para não crescer o custo a cada pergunta.
        if len(self.historico) > self.limite_de_turnos * 2:
            self.historico = self.historico[-self.limite_de_turnos * 2 :]

        return texto
