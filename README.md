# Jarvis

Assistente pessoal em português: escuta, entende e responde falando.

Voz e reconhecimento de fala rodam **100% offline** na máquina —
[Piper](https://github.com/rhasspy/piper) para falar,
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) para ouvir. Nenhum
áudio sai do computador. A conversa aberta com o Claude é opcional e é a única
parte que usa a internet.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python scripts/baixar_voz.py    # baixa a voz pt_BR-faber-medium
```

O modelo de escuta (whisper-small, ~500 MB) é baixado sozinho na primeira vez
que você usar `--ouvir`.

## Uso

```bash
python -m jarvis                    # conversa por texto, responde em voz
python -m jarvis --ouvir            # conversa por voz, de ponta a ponta
python -m jarvis --mudo             # só texto, sem áudio
python -m jarvis --offline          # sem consultar o Claude
python -m jarvis --dizer "bom dia"  # responde uma frase e sai
```

Cada peça que falta desativa só a si mesma: sem o modelo de voz o Jarvis
responde por texto, sem credencial da Anthropic ele fica só nos comandos
locais, e avisa em ambos os casos como habilitar.

## O que ele entende

| Comando | Exemplos |
| --- | --- |
| saudação | "bom dia", "oi", "e aí" |
| horas | "que horas são" |
| data | "que dia é hoje" |
| volume | "aumentar o volume", "abaixa o som", "fica mudo" |
| abrir | "abrir a calculadora", "abre o youtube" |
| pesquisar | "pesquisar por receita de bolo" |
| bloquear | "bloquear o computador" |
| ajuda | "ajuda", "o que você faz" |
| encerrar | "tchau", "desligar" |

Qualquer outra frase vai para o Claude, se houver credencial configurada.

Os gatilhos são comparados sem acento, sem pontuação e por palavra inteira —
"que horas são" e "que horas sao" funcionam igual, e "depois" não dispara a
saudação por conter "oi".

## Conversa aberta (opcional)

Para o Jarvis responder qualquer pergunta, e não só os comandos acima,
configure uma credencial da Anthropic:

```bash
setx ANTHROPIC_API_KEY "sua-chave"      # ou: ant auth login
```

Usa o modelo `claude-opus-5` ($5 por milhão de tokens de entrada, $25 de
saída), com esforço baixo e respostas de duas a três frases — o texto é falado
em voz alta, então respostas longas atrapalham. O histórico guarda os últimos
12 turnos. Sem credencial nada disso é acionado e nenhum dado sai da máquina.

## Vozes disponíveis

```bash
python scripts/baixar_voz.py --listar
```

| Modelo | Idioma | Timbre |
| --- | --- | --- |
| `pt_BR-faber-medium` | português brasileiro | masculina, grave (padrão) |
| `pt_BR-cadu-medium` | português brasileiro | masculina |
| `pt_BR-jeff-medium` | português brasileiro | masculina |
| `pt_BR-edresson-low` | português brasileiro | masculina, modelo leve |
| `pt_PT-tugão-medium` | português de Portugal | masculina |

Para trocar, baixe o modelo e ajuste a configuração:

```bash
python scripts/baixar_voz.py pt_BR-jeff-medium
python -m jarvis --voz pt_BR-jeff-medium     # teste rápido
```

Para fixar, crie `config.local.json` na raiz (ignorado pelo git):

```json
{
  "voz": "pt_BR-jeff-medium",
  "tratamento": "chefe",
  "modelo_de_escuta": "medium",
  "limiar_de_silencio": 0.02,
  "exigir_palavra_de_ativacao": true
}
```

## Ajustando a escuta

| Configuração | Para quê |
| --- | --- |
| `modelo_de_escuta` | `base` (rápido), `small` (padrão), `medium` (preciso, lento) |
| `limiar_de_silencio` | suba se ele gravar sozinho num ambiente barulhento; desça se não ouvir você |
| `silencio_para_encerrar` | segundos de silêncio que encerram a fala (padrão: 1) |
| `exigir_palavra_de_ativacao` | só responde se a frase começar com "Jarvis" |

## Estrutura

```
jarvis/
├── __main__.py        ponto de entrada, laços de texto e de voz
├── configuracoes.py   padrões + config.local.json
├── voz.py             fala com o Piper
├── ouvido.py          escuta com o faster-whisper e detector de silêncio
├── cerebro.py         roteia a frase: comando local ou Claude
├── conversa.py        conversa aberta com o Claude (opcional)
└── comandos/
    ├── base.py        classe Comando e normalização de texto
    ├── basicos.py     saudação, horas, data, ajuda, encerrar
    └── sistema.py     abrir programas, volume, busca, bloquear
scripts/
└── baixar_voz.py      baixa modelos do catálogo do Piper
modelos/               modelos de voz e de escuta (fora do git)
```

## Criando um comando novo

Em `jarvis/comandos/`, crie a subclasse e registre a instância em
`comandos/__init__.py` (a ordem importa — o primeiro que aceitar responde):

```python
from .base import Comando

class Clima(Comando):
    nome = "clima"
    descricao = "Informa a previsão do tempo."
    gatilhos = ("previsao do tempo", "vai chover", "clima")

    def executar(self, frase: str, config: dict) -> str:
        return f"Céu limpo hoje, {config['tratamento']}."
```

## Próximos passos

- [ ] Palavra de ativação sempre escutando, sem precisar rodar `--ouvir`
- [ ] Lembretes e temporizadores
- [ ] Controle de música (Spotify)
- [ ] Iniciar junto com o Windows, em segundo plano
