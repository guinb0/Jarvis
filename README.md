# Jarvis

Assistente pessoal em português, rodando 100% offline na máquina local.

A voz é sintetizada pelo [Piper](https://github.com/rhasspy/piper) com modelos
em português brasileiro — nada é enviado para a nuvem.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Baixe a voz padrão (`pt_BR-faber-medium`, masculina, brasileira):

```bash
python scripts/baixar_voz.py
```

## Uso

```bash
python -m jarvis                    # conversa por texto, responde em voz
python -m jarvis --mudo             # só texto, sem áudio
python -m jarvis --dizer "bom dia"  # responde uma frase e sai
```

Sem o modelo de voz baixado, o Jarvis continua funcionando em modo texto e
avisa como habilitar o áudio.

## Vozes disponíveis

| Modelo | Idioma | Timbre |
| --- | --- | --- |
| `pt_BR-faber-medium` | português brasileiro | masculino, grave (padrão) |
| `pt_BR-edresson-low` | português brasileiro | masculino, mais leve |
| `pt_PT-tugão-medium` | português de Portugal | masculino |

Para trocar, baixe o modelo e aponte a configuração para ele:

```bash
python scripts/baixar_voz.py pt_PT-tugão-medium
```

`config.local.json` na raiz (ignorado pelo git):

```json
{
  "voz": "pt_PT-tugão-medium",
  "tratamento": "chefe"
}
```

## Estrutura

```
jarvis/
├── __main__.py        ponto de entrada e laço de conversa
├── configuracoes.py   padrões + config.local.json
├── voz.py             síntese de voz com Piper
├── cerebro.py         roteia a frase para o comando certo
└── comandos/
    ├── base.py        classe Comando e normalização de texto
    └── basicos.py     saudação, horas, data, ajuda, encerrar
scripts/
└── baixar_voz.py      baixa modelos do repositório rhasspy/piper-voices
modelos/               modelos .onnx (fora do git)
```

## Criando um comando novo

Em `jarvis/comandos/`, crie a subclasse e registre a instância em
`comandos/__init__.py`:

```python
from .base import Comando

class Clima(Comando):
    nome = "clima"
    descricao = "Informa a previsão do tempo."
    gatilhos = ("previsao do tempo", "vai chover", "clima")

    def executar(self, frase: str, config: dict) -> str:
        return f"Céu limpo hoje, {config['tratamento']}."
```

Os gatilhos são comparados sem acento, sem pontuação e em minúsculas — basta
escrevê-los na forma mais natural.

## Próximos passos

- [ ] Reconhecimento de fala (ouvido) com Whisper ou Vosk
- [ ] Palavra de ativação ("Jarvis") sempre escutando
- [ ] Comandos de sistema: abrir programas, controlar volume
- [ ] Integração com um modelo de linguagem para conversas abertas
