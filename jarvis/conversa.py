"""Conversa aberta com o Claude, para quando nenhum comando local responde.

É opcional: sem credencial da Anthropic o Jarvis segue funcionando só com os
comandos offline. A credencial vem da variável de ambiente ANTHROPIC_API_KEY
ou de um perfil criado com `ant auth login` — nenhuma chave fica no código.

Roteamento de dois níveis (quando `usar_roteador_leve` está ligado):
- Haiku: conversa fiada e confirmações, onde errar pouco custa pouco.
- Sonnet: número, grafia, fato, raciocínio e qualquer busca na web.

A regra é conservadora — na dúvida vai pro Sonnet. Se o Haiku errar, diga
"confere isso" / "tem certeza" e o pedido sobe pro Sonnet.
"""

from __future__ import annotations

import re
import sys

from .comandos.base import normalizar

# Sonnet 5: respostas faladas de duas ou três frases, onde a diferença de
# capacidade quase não aparece e o crédito rende bem.
MODELO_FORTE = "claude-sonnet-5"
MODELO_LEVE = "claude-haiku-4-5"

# Compatível com quem ainda importa MODELO do módulo.
MODELO = MODELO_FORTE

# O Jarvis fala as respostas em voz alta, então elas precisam ser curtas:
# um parágrafo falado já é longo demais.
INSTRUCOES = """Você é o Jarvis, o assistente pessoal do usuário, e responde sempre em \
português brasileiro.

Suas respostas são convertidas em fala (TTS). Por isso:
- Responda em no máximo duas frases curtas.
- Escreva números, datas e unidades por extenso quando forem curtos.
- Só texto corrido. Sem listas, marcadores, tabelas, emoji, markdown ou aspas.
- Nunca use hífen, travessão, dois-pontos, ponto-e-vírgula, barra ou parênteses. \
Use vírgula ou ponto para pausar.
- Sem preâmbulo. Responda direto.
- Se a fala do usuário parecer truncada, mal ouvida ou ambígua, diga só \
"Não peguei, pode repetir?" — não invente opções nem faça menu de esclarecimento.
- Cumprimentos e "tudo bem" são conversa, não pergunta técnica.

Trate o usuário por "{tratamento}". Seja direto, esperto e cordial, sem bajulação. \
Se não souber algo, diga isso em uma frase em vez de inventar.

Quando houver um bloco de "Memória local do usuário", trate como fatos e \
preferências dele: use se for relevante, não contradiga sem motivo, e não \
invente detalhes que não estejam lá.

Você tem acesso à internet pela ferramenta de busca. Use quando a resposta \
depender de informação atual — notícias, cotações, placares, previsão do \
tempo, preços, horários, lançamentos — ou quando o usuário pedir para \
procurar. Não use para o que você já sabe. Ao usar, diga em poucas palavras \
de onde veio a informação, sem ler endereços de sites em voz alta."""

# Mesmas regras de fala, sem ferramenta de busca — o Haiku não pesquisa.
INSTRUCOES_LEVES = """Você é o Jarvis, o assistente pessoal do usuário, e responde sempre em \
português brasileiro.

Suas respostas são convertidas em fala (TTS). Por isso:
- Responda em no máximo duas frases curtas.
- Só texto corrido. Sem listas, markdown, emoji, hífen, travessão, dois-pontos \
ou parênteses. Use vírgula ou ponto para pausar.
- Sem preâmbulo. Responda direto.
- Se não entender a fala, diga só "Não peguei, pode repetir?" — sem menus.
- Cumprimentos e "tudo bem" / "beleza" / "valeu" são conversa leve: responda \
na mesma linha, sem perguntar o que a pessoa quis dizer.

Trate o usuário por "{tratamento}". Seja direto e cordial, sem bajulação. \
Você só atende conversa leve e confirmações. Se o pedido exigir número, \
cálculo, ortografia, fato verificável ou informação atual, diga em uma \
frase que vai precisar conferir — não invente."""

# Buscas em página web custam à parte da conversa: cerca de US$ 10 por mil
# buscas, além dos tokens do conteúdo lido. Por isso o teto de usos por
# pergunta — sem ele, uma pesquisa poderia render dez buscas.
FERRAMENTAS_DE_WEB = [
    # Pesquisa e devolve trechos das páginas encontradas.
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 3},
    # Abre por inteiro uma página que já apareceu na conversa, quando o trecho
    # da busca não basta. Só alcança endereços que a busca trouxe.
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 3},
]

# Quantas vezes reenviar quando a busca no servidor pausa antes de concluir.
RETOMADAS_MAXIMAS = 3

# Pedidos que sobem pro Sonnet mesmo depois de uma resposta do Haiku.
GATILHOS_DE_ESCAPE = (
    "confere",
    "confere isso",
    "tem certeza",
    "tem certeza disso",
    "confirma",
    "confirma isso",
    "checa isso",
    "checa pra mim",
    "verifica",
    "verifica isso",
    "isso esta certo",
    "isso ta certo",
    "olha de novo",
)

# Só nestes casos o Haiku responde. Qualquer outra coisa — inclusive o que
# "parece" trivial — vai pro Sonnet: ortografia e conta simples já enganaram.
GATILHOS_DE_CONVERSA_LEVE = (
    "obrigado",
    "obrigada",
    "valeu",
    "thanks",
    "entendi",
    "beleza",
    "blz",
    "tudo bem",
    "tudo bom",
    "como vai",
    "como voce esta",
    "como voce ta",
    "boa",
    "legal",
    "show",
    "ok",
    "okay",
    "certo",
    "fechado",
    "combinado",
    "pode ser",
    "ah ta",
    "sim",
    "nao",
    "isso",
    "isso mesmo",
    "perfeito",
    "otimo",
    "incrivel",
    "top",
    "massa",
    "uhum",
    "hmm",
    "repetir",
    "repete",
    "fala de novo",
    "diz de novo",
    "o que voce disse",
    "o que voce falou",
    "nao entendi o que voce disse",
)

# Pedidos que pedem busca na web — só aí anexamos as ferramentas (elas
# deixam o Sonnet mais lento mesmo quando ele não as usa).
GATILHOS_DE_BUSCA = (
    "pesquis",
    "busca",
    "procure",
    "procura",
    "google",
    "noticia",
    "noticias",
    "cotacao",
    "dolar",
    "euro",
    "bitcoin",
    "previsao",
    "tempo em",
    "clima",
    "placar",
    "resultado do",
    "lancamento",
    "hoje em dia",
    "agora mesmo",
    "na internet",
    "no google",
)

# "O que abriu?" depois que o Jarvis abriu fontes no navegador.
GATILHOS_O_QUE_ABRIU = (
    "que abriu",
    "que que abriu",
    "que que se abriu",
    "o que abriu",
    "o que se abriu",
    "que pagina",
    "que site",
    "que fonte",
    "quais fontes",
    "o que voce abriu",
    "o que vc abriu",
)


class SemCredencial(Exception):
    """Não há credencial da Anthropic configurada nesta máquina."""


def fontes_consultadas(resposta) -> list[str]:
    """Endereços que a busca trouxe, na ordem, sem repetição.

    Em caso de erro da ferramenta o `content` vem como um objeto de erro em vez
    de lista — por isso a checagem antes de percorrer.
    """
    urls: list[str] = []
    for bloco in getattr(resposta, "content", []):
        if getattr(bloco, "type", None) != "web_search_tool_result":
            continue
        conteudo = getattr(bloco, "content", None)
        if not isinstance(conteudo, list):
            continue  # a ferramenta falhou; não há fontes a mostrar
        for achado in conteudo:
            url = getattr(achado, "url", None)
            if url and url not in urls:
                urls.append(url)
    return urls


# Fim de frase: pontuação seguida de espaço. Só corta depois de um mínimo de
# caracteres, para não picar abreviações ("Dr. Silva") em duas falas.
_FIM_DE_FRASE = re.compile(r"[.!?…](?=\s)")
_MINIMO_POR_FRASE = 25


def _cortar_frase(acumulado: str) -> tuple[str | None, str]:
    """Separa a primeira frase completa do que chegou até agora.

    Devolve (frase, resto). Frase é None enquanto nenhuma fechou.
    """
    for achado in _FIM_DE_FRASE.finditer(acumulado):
        if achado.end() >= _MINIMO_POR_FRASE:
            return acumulado[: achado.end()].strip(), acumulado[achado.end() :]
    return None, acumulado


def disponivel() -> bool:
    """Diz se a biblioteca da Anthropic está instalada."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _e_escape(frase: str) -> bool:
    normal = normalizar(frase)
    return any(
        re.search(rf"\b{re.escape(normalizar(g))}\b", normal)
        for g in GATILHOS_DE_ESCAPE
    )


def _e_conversa_leve(frase: str) -> bool:
    """Só True quando o pedido é claramente fiada/confirmação.

    Conservador de propósito: na dúvida devolve False e o Sonnet assume.
    Frases bem curtas sem número e sem cara de pergunta factual também
    vão pro Haiku — evita esperar o Sonnet só pra ouvir "não entendi".
    """
    normal = normalizar(frase)
    if not normal or _e_escape(frase):
        return False
    # Número na frase → Sonnet (contas e cotações já quebraram o Haiku).
    if re.search(r"\d", frase):
        return False
    if any(
        re.search(rf"\b{re.escape(normalizar(g))}\b", normal)
        for g in GATILHOS_DE_CONVERSA_LEVE
    ):
        return True
    # Frase bem curta sem cara de pergunta: Haiku responde rápido.
    palavras = normal.split()
    if len(palavras) <= 3 and not _precisa_web(frase):
        # Evita mandar "quanto é" / "quem foi" / "onde fica" pro Haiku.
        if any(
            p in palavras
            for p in (
                "quanto",
                "quantos",
                "quantas",
                "quem",
                "onde",
                "quando",
                "porque",
                "porquê",
                "qual",
                "quais",
                "como",
                "explica",
                "calcule",
                "escreve",
                "escreva",
                "que",
                "abre",
                "abrir",
                "pesquisa",
                "tarefas",
                "github",
            )
        ):
            return False
        return True
    return False


def _precisa_web(frase: str) -> bool:
    """True quando vale a pena anexar as ferramentas de busca."""
    normal = normalizar(frase)
    return any(normalizar(g) in normal for g in GATILHOS_DE_BUSCA)


def _perguntou_o_que_abriu(frase: str) -> bool:
    normal = normalizar(frase)
    return any(normalizar(g) in normal for g in GATILHOS_O_QUE_ABRIU)


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

        tratamento = config["tratamento"]
        self.instrucoes = INSTRUCOES.format(tratamento=tratamento)
        self.instrucoes_leves = INSTRUCOES_LEVES.format(tratamento=tratamento)
        self.limite_de_turnos = limite_de_turnos
        self.buscar_na_web = config["buscar_na_web"]
        self.abrir_fontes = config["abrir_fontes_no_navegador"]
        self.usar_roteador_leve = config.get("usar_roteador_leve", True)
        self.historico: list[dict] = []
        # Qual modelo atendeu o último pedido — útil pra medir o roteador.
        self.ultimo_modelo: str | None = None
        # Últimas URLs abertas no navegador — pra responder "o que abriu?".
        self.ultimas_fontes: list[str] = []

        from . import memoria as modulo_memoria

        self.memoria = modulo_memoria.carregar(config)
        # Espelha os repos do GitHub na memória vetorial (no máx. 1x/dia).
        try:
            from . import github_cliente as gh

            gh.garantir_memoria_projetos(config, self.memoria)
        except Exception as erro:  # noqa: BLE001
            print(f"[conversa] sync GitHub: {erro}", file=sys.stderr)

    def _mostrar_fontes(self, resposta) -> None:
        """Abre no navegador as páginas que embasaram a resposta.

        O Jarvis roda sem janela e responde só por voz; sem isto não haveria
        como conferir de onde veio a informação.
        """
        todas = fontes_consultadas(resposta)
        if todas:
            # Guarda mesmo se não for abrir no navegador — serve pro "o que abriu?".
            self.ultimas_fontes = todas[: max(self.abrir_fontes, 2)]

        if not self.abrir_fontes:
            return

        urls = todas[: self.abrir_fontes]
        if not urls:
            return

        import webbrowser

        for url in urls:
            try:
                webbrowser.open(url)
            except OSError as erro:
                print(f"[conversa] não abri {url}: {erro}", file=sys.stderr)

    def _responder_o_que_abriu(self) -> str | None:
        """Resposta local rápida quando perguntam pelas abas abertas."""
        if not self.ultimas_fontes:
            return None
        from urllib.parse import urlparse

        nomes = []
        for url in self.ultimas_fontes:
            host = urlparse(url).netloc.removeprefix("www.")
            if host and host not in nomes:
                nomes.append(host)
        if not nomes:
            return None
        if len(nomes) == 1:
            return f"Abri a página do {nomes[0]}, senhor."
        lista = ", ".join(nomes[:-1]) + f" e {nomes[-1]}"
        return f"Abri as páginas de {lista}, senhor."

    def _escolher_modelo(self, frase: str) -> str:
        """Devolve Haiku só no que é seguro; Sonnet no resto e nos escapes."""
        if not self.usar_roteador_leve:
            return MODELO_FORTE
        if _e_escape(frase) or not _e_conversa_leve(frase):
            return MODELO_FORTE
        return MODELO_LEVE

    def _frase_para_modelo(self, frase: str, modelo: str) -> str:
        """No escape, manda o Sonnet rever o último pedido em vez de 'confere'."""
        if modelo != MODELO_FORTE or not _e_escape(frase):
            return frase

        ultimo_pedido = next(
            (
                m["content"]
                for m in reversed(self.historico)
                if m["role"] == "user"
            ),
            None,
        )
        if not ultimo_pedido:
            return frase

        return (
            f"Confira com cuidado a resposta anterior sobre isto: {ultimo_pedido}. "
            f"O usuário disse: {frase}"
        )

    def _sistema_com_memoria(self, base: str, frase: str, modelo: str) -> str:
        """Acrescenta trechos locais relevantes ao system prompt, se houver.

        No Haiku pula a busca vetorial — o embedding local atrasa a resposta
        e conversa leve quase nunca precisa da memória.
        """
        if not self.memoria or modelo == MODELO_LEVE:
            return base
        contexto = self.memoria.contexto_para_prompt(frase)
        if not contexto:
            return base
        return f"{base}\n\n{contexto}"

    def _chamar(self, mensagens: list[dict], modelo: str, sistema: str, usar_web: bool):
        """Faz a chamada; Haiku sem raciocínio adaptativo (ele não aceita)."""
        comum = dict(
            model=modelo,
            max_tokens=1024 if modelo == MODELO_LEVE else 2048,
            system=sistema,
            messages=mensagens,
        )

        if modelo != MODELO_LEVE:
            # Raciocínio leve: o modelo pensa só o necessário e responde rápido.
            comum["thinking"] = {"type": "adaptive"}
            comum["output_config"] = {"effort": "low"}
            if self.buscar_na_web and usar_web:
                # As duas rodam no servidor da Anthropic: ela pesquisa, abre as
                # páginas e devolve tudo na mesma resposta. Não há raspador aqui,
                # nada que quebre quando um site muda de layout.
                comum["tools"] = FERRAMENTAS_DE_WEB

        try:
            return self.cliente.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                **comum,
            )
        except self.anthropic.BadRequestError:
            # Conta sem acesso ao desvio automático: segue sem ele.
            return self.cliente.messages.create(**comum)

    def responder_em_partes(self, frase: str):
        """Vai entregando a resposta em frases, conforme o Claude a escreve.

        Só transmite no caminho simples. Com busca na web a resposta passa por
        rodadas de ferramenta no servidor e pode pausar no meio; ali vale mais
        a lógica de retomada já testada do `responder`, que devolve tudo pronto.
        """
        import time

        if _perguntou_o_que_abriu(frase):
            local = self._responder_o_que_abriu()
            if local:
                print("[conversa] fontes-locais", file=sys.stderr)
                yield local
                return

        modelo = self._escolher_modelo(frase)
        usar_web = modelo == MODELO_FORTE and _precisa_web(frase)
        if usar_web:
            yield self.responder(frase)
            return

        inicio = time.perf_counter()
        pedido = self._frase_para_modelo(frase, modelo)
        base = self.instrucoes_leves if modelo == MODELO_LEVE else self.instrucoes
        sistema = self._sistema_com_memoria(base, frase, modelo)
        mensagens = self.historico + [{"role": "user", "content": pedido}]

        comum = dict(
            model=modelo,
            max_tokens=1024 if modelo == MODELO_LEVE else 2048,
            system=sistema,
            messages=mensagens,
        )
        if modelo != MODELO_LEVE:
            comum["thinking"] = {"type": "adaptive"}
            comum["output_config"] = {"effort": "low"}

        primeira = None
        inteiro: list[str] = []
        acumulado = ""

        try:
            with self.cliente.messages.stream(**comum) as fluxo:
                for pedaco in fluxo.text_stream:
                    acumulado += pedaco
                    while True:
                        pronta, acumulado = _cortar_frase(acumulado)
                        if pronta is None:
                            break
                        if primeira is None:
                            primeira = time.perf_counter() - inicio
                        inteiro.append(pronta)
                        yield pronta

                if acumulado.strip():
                    if primeira is None:
                        primeira = time.perf_counter() - inicio
                    inteiro.append(acumulado.strip())
                    yield acumulado.strip()
        except self.anthropic.AuthenticationError:
            yield "Não estou conectado à nuvem: falta configurar a credencial da Anthropic."
            return
        except self.anthropic.RateLimitError:
            yield "Estou recebendo pedidos demais. Tente de novo em instantes."
            return
        except self.anthropic.APIConnectionError:
            yield "Não consegui acessar a internet agora."
            return
        except self.anthropic.APIStatusError as erro:
            print(f"[conversa] erro {erro.status_code}: {erro.message}", file=sys.stderr)
            yield "Deu problema ao consultar a nuvem."
            return

        texto = " ".join(inteiro).strip()
        if not texto:
            yield "Não consegui formular uma resposta."
            return

        self.ultimo_modelo = modelo
        print(
            f"[conversa] {modelo} fluxo 1a frase {primeira:.1f}s "
            f"total {time.perf_counter() - inicio:.1f}s",
            file=sys.stderr,
        )

        self.historico = self.historico + [
            {"role": "user", "content": frase},
            {"role": "assistant", "content": texto},
        ]
        if len(self.historico) > self.limite_de_turnos * 2:
            self.historico = self.historico[-self.limite_de_turnos * 2 :]

    def responder(self, frase: str) -> str:
        import time

        # "Que que se abriu?" depois de abrir fontes — resposta local, sem API.
        if _perguntou_o_que_abriu(frase):
            local = self._responder_o_que_abriu()
            if local:
                print("[conversa] fontes-locais", file=sys.stderr)
                return local

        inicio = time.perf_counter()
        modelo = self._escolher_modelo(frase)
        pedido = self._frase_para_modelo(frase, modelo)
        base = self.instrucoes_leves if modelo == MODELO_LEVE else self.instrucoes
        sistema = self._sistema_com_memoria(base, frase, modelo)
        mensagens = self.historico + [{"role": "user", "content": pedido}]
        usar_web = modelo == MODELO_FORTE and _precisa_web(frase)

        try:
            resposta = self._chamar(mensagens, modelo, sistema, usar_web)

            # A busca roda no servidor e pausa ao atingir o limite de rodadas.
            # Reenviar a conversa retoma de onde parou; o teto evita laço
            # infinito se ela nunca concluir.
            if modelo == MODELO_FORTE and usar_web:
                for _ in range(RETOMADAS_MAXIMAS):
                    if resposta.stop_reason != "pause_turn":
                        break
                    mensagens = mensagens + [
                        {"role": "assistant", "content": resposta.content}
                    ]
                    resposta = self._chamar(mensagens, modelo, sistema, usar_web)
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

        self.ultimo_modelo = modelo
        print(
            f"[conversa] {modelo} web={'sim' if usar_web else 'não'} "
            f"{time.perf_counter() - inicio:.1f}s",
            file=sys.stderr,
        )

        if modelo == MODELO_FORTE:
            self._mostrar_fontes(resposta)

        # Guarda a frase original do usuário (não o prompt de escape), para o
        # histórico continuar natural na próxima vez.
        self.historico = self.historico + [
            {"role": "user", "content": frase},
            {"role": "assistant", "content": texto},
        ]
        # Mantém a memória curta para não crescer o custo a cada pergunta.
        if len(self.historico) > self.limite_de_turnos * 2:
            self.historico = self.historico[-self.limite_de_turnos * 2 :]

        return texto
