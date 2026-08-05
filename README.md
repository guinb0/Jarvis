# Jarvis

Assistente pessoal em português: escuta, entende e responde falando.

O reconhecimento de fala roda **sempre na máquina**, com
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) — nenhum áudio sai
do computador, nunca.

Para falar há dois motores. O padrão é o **Edge TTS**, com vozes neurais que
soam naturais; em troca, o *texto* da resposta é enviado para a Microsoft. O
outro é o [Piper](https://github.com/rhasspy/piper), que sintetiza aqui dentro
sem tocar na rede, ao custo de um timbre bem mais robótico. Se a internet cair,
o Jarvis passa sozinho para o Piper.

Quer tudo offline? `python -m jarvis --motor piper` — ou fixe `"motor": "piper"`
no `config.local.json`.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

A voz padrão já funciona assim, sem download — as vozes da Edge são sintetizadas
do lado da Microsoft. Só o motor offline precisa de modelo:

```bash
python scripts/baixar_voz.py    # baixa pt_BR-faber-medium (~60 MB), a reserva
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
python -m jarvis --motor piper      # voz offline, sem internet
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
| jogo | "abrir dead by daylight", "jogar phasmophobia", "joga dbd" |
| abrir | "abrir a calculadora", "abre o youtube" |
| pesquisar | "pesquisar por receita de bolo" |
| tarefas (TickTick) | "tarefas de hoje", "criar tarefa comprar café", "já bebi água" |
| relatório semanal | "relatório da semana", "minha produtividade" |
| github | "status do github", "notificações do github", "meus pull requests", "minhas issues" |
| bloquear | "bloquear o computador" |
| ajuda | "ajuda", "o que você faz" |
| encerrar | "tchau", "desligar" |

Qualquer outra frase vai para o Claude, se houver credencial configurada.
Com a conversa aberta, pedidos de pesquisa ("pesquisar bitcoin", "quanto está
o dólar", "notícias de hoje") usam a busca na web do Claude: ele lê páginas,
responde em voz alta e abre as fontes no navegador. Sem credencial, "pesquisar"
ainda abre o Google como antes.

Os gatilhos são comparados sem acento, sem pontuação e por palavra inteira —
"que horas são" e "que horas sao" funcionam igual, e "depois" não dispara a
saudação por conter "oi".

## Jogos

A lista de jogos não fica no código: o Jarvis lê os jogos instalados do Steam
(inclusive bibliotecas em outros discos) e da Epic na primeira vez que você pede
um. Instalou um jogo novo? Ele já funciona, sem editar nada.

```
abrir dead by daylight        jogar phasmophobia        joga dbd
```

O lançamento é sempre pela loja (`steam://`, `com.epicgames.launcher://`), nunca
pelo .exe direto — é assim que a loja cuida de login, saves na nuvem e patches.

Duas regras de reconhecimento: é preciso um **verbo** ("abrir", "jogar",
"inicia"...) junto do nome, senão "o que é dead by daylight?" abriria o jogo em
vez de virar pergunta; e o nome pode ser parcial, então "plants vs zombies"
acha o jogo sem você recitar "garden warfare 2 deluxe edition".

Apelidos falados ficam em `APELIDOS`, em [jogos.py](jarvis/comandos/jogos.py) —
`dbd`, `cs2`, `repo` já vêm prontos.

## Iniciar junto com o Windows

```bash
powershell -ExecutionPolicy Bypass -File scripts\instalar_inicializacao.ps1
```

Cria um atalho na pasta Inicializar do seu usuário (não precisa de
administrador). A cada login o Jarvis sobe **sem janela nenhuma**, já escutando.

Não ter janela é de propósito. Um jogo em tela cheia exclusiva esconde todas as
outras janelas, e a do Jarvis reaparecia só ao sair do jogo — parecia que ele
fechava e reabria sozinho, quando na verdade seguia rodando o tempo todo. Sem
janela, não há o que sumir.

| Para | Comando |
| --- | --- |
| ver o que ele está fazendo | `Get-Content jarvis.log -Tail 20 -Wait` |
| encerrar | `powershell -File scripts\parar_jarvis.ps1` |
| desligar a inicialização | `powershell -File scripts\instalar_inicializacao.ps1 -Remover` |
| rodar com janela, para depurar | `scripts\iniciar_jarvis.bat` |

Para mudar como ele inicia — modo texto, voz offline — edite a última linha de
[scripts/iniciar_jarvis.bat](scripts/iniciar_jarvis.bat), que é o arquivo que
tanto o modo oculto quanto o modo com janela executam.

Em modo de escuta ele segura o microfone e ocupa cerca de 1 GB de RAM com o
whisper-small carregado.

Se outro programa tomar o microfone em modo exclusivo, o Jarvis reclama cinco
vezes e depois segue tentando em silêncio, para sempre — ele nunca se encerra
sozinho por causa disso, e avisa "microfone de volta" quando recupera.

## Conversa aberta (opcional)

Para o Jarvis responder qualquer pergunta, e não só os comandos acima,
configure uma credencial da Anthropic:

```bash
setx ANTHROPIC_API_KEY "sua-chave"      # ou: ant auth login
```

Usa o modelo `claude-sonnet-5`, com esforço baixo e respostas de duas a três
frases — o texto é falado em voz alta, então respostas longas atrapalham. O
histórico guarda os últimos 12 turnos. Sem credencial nada disso é acionado e
nenhum dado sai da máquina.

Com `"buscar_na_web": true` (padrão), o Claude pesquisa e abre páginas quando
a resposta depende de informação atual ou quando você pede para procurar.
As fontes abrem no navegador (`abrir_fontes_no_navegador`, padrão: 2). Desligue
a busca com `"buscar_na_web": false` no `config.local.json`.

### Roteador Haiku / Sonnet

Com `"usar_roteador_leve": true` (padrão), a conversa aberta se divide:

| Modelo | Quando |
| --- | --- |
| `claude-haiku-4-5` | conversa fiada e confirmações ("obrigado", "beleza", "repete") |
| `claude-sonnet-5` | número, ortografia, fato, raciocínio e **toda** busca na web |

A regra é conservadora: na dúvida vai pro Sonnet. Se o Haiku errar, diga
"confere isso" ou "tem certeza" — o pedido sobe pro Sonnet. Desligue com
`"usar_roteador_leve": false` para mandar tudo ao Sonnet.

Custo medido neste formato de resposta, com US$ 5 de crédito:

| Modelo | Por pergunta | Perguntas com US$ 5 |
| --- | --- | --- |
| `claude-sonnet-5` | US$ 0,0019 | ~2.690 |
| `claude-haiku-4-5` (só fiada) | ~US$ 0,0006 | ~8.000 |
| `claude-opus-5` | US$ 0,0057 | ~880 |

Haiku **não** usa raciocínio adaptativo nem ferramentas de busca — só o Sonnet.

### Memória local (SQLite)

Não é fine-tuning e **não usa .md como banco**. Os embeddings ficam na tabela
`memorias` de um arquivo SQLite: `modelos/memoria.db`. Sem servidor, sem Docker
— abre sempre.

```bash
pip install -r requirements.txt      # fastembed (SQLite já vem com o Python)
python scripts/indexar_memoria.py     # semeia estilo/preferencias se vazios
python scripts/indexar_memoria.py --buscar "como voce deve falar"
python scripts/indexar_memoria.py --adicionar preferencias "Não usar emoji."
```

Caminho em `memoria_banco` no `config.local.json` (vazio = o padrão acima).
Desligue com `"usar_memoria": false`.

A busca por similaridade roda em numpy sobre os vetores carregados: **5 a 30 ms**
por consulta. Era pgvector no Postgres antes, mas o índice aproximado só compensa
com milhões de vetores — e exigir o Docker de pé fazia a memória simplesmente
não subir quando ele estava desligado.

A pasta `memoria/*.md` é só semente opcional da 1ª carga — o índice vivo é o banco.

### TickTick

Lista, cria e conclui tarefas por voz via [Open API](https://developer.ticktick.com/).

1. Crie um app em https://developer.ticktick.com/manage
2. Redirect URL: `http://127.0.0.1:8765/callback`
3. Coloque `ticktick_client_id` e `ticktick_client_secret` no `config.local.json`
4. Autorize uma vez:

```bash
python scripts/autorizar_ticktick.py
```

Exemplos: `tarefas de hoje`, `criar tarefa estudar amanhã`, `já bebi água`,
`já fiz atividade física`, `relatório da semana`, `minha produtividade`.

Com `"ticktick_cobrar": true` (padrão) ele lembra das pendentes a cada
`"ticktick_cobrar_minutos"` (padrão: 60), inclusive dormindo — desligue com
`"ticktick_cobrar_dormindo": false` se atrapalhar no jogo.

Todo domingo às 20h (ajustável) ele fala sozinho o **relatório semanal**:
quantas tarefas concluiu, destaques (hábitos) e o que ainda está em aberto.
`"ticktick_relatorio_dia"`: 0=segunda … 6=domingo; `"ticktick_relatorio_hora"`: 0–23.

### GitHub

1. Crie um **Personal Access Token (classic)** em  
   https://github.com/settings/tokens  
   Escopos: `notifications` e `repo` (ou `public_repo` se só repos públicos).
2. No `config.local.json`:

```json
"github_token": "ghp_...."
```

Exemplos: `status do github`, `notificações do github`, `meus pull requests`,
`minhas issues`, `meus projetos`.

A lista de repositórios também vai para a tabela `memorias` (origem
`github:projetos`), para o Claude saber dos seus projetos. Atualiza no máximo
1×/dia, ou force com:

```bash
python scripts/sincronizar_github.py
```

## Vozes disponíveis

```bash
python scripts/baixar_voz.py --listar
```

### Motor `edge` — naturais, pela internet

Não precisam ser baixadas.

| Voz | Idioma | Timbre |
| --- | --- | --- |
| `pt-BR-ThalitaMultilingualNeural` | português brasileiro | feminina, a mais natural (padrão) |
| `pt-BR-FranciscaNeural` | português brasileiro | feminina |
| `pt-BR-AntonioNeural` | português brasileiro | masculina |
| `pt-PT-RaquelNeural` | português de Portugal | feminina |
| `pt-PT-DuarteNeural` | português de Portugal | masculina |

### Motor `piper` — offline, mais robóticas

Todas masculinas: o Piper não tem voz feminina em português.

| Modelo | Idioma | Timbre |
| --- | --- | --- |
| `pt_BR-faber-medium` | português brasileiro | masculina, grave (padrão do motor) |
| `pt_BR-cadu-medium` | português brasileiro | masculina |
| `pt_BR-jeff-medium` | português brasileiro | masculina |
| `pt_BR-edresson-low` | português brasileiro | masculina, modelo leve |
| `pt_PT-tugão-medium` | português de Portugal | masculina |

Para testar rápido:

```bash
python -m jarvis --voz pt-BR-AntonioNeural --dizer "bom dia"
python -m jarvis --motor piper --voz pt_BR-jeff-medium --dizer "bom dia"
```

Para fixar, crie `config.local.json` na raiz (ignorado pelo git):

```json
{
  "motor": "edge",
  "voz_edge": "pt-BR-FranciscaNeural",
  "voz_piper": "pt_BR-jeff-medium",
  "tratamento": "chefe",
  "modelo_de_escuta": "medium",
  "limiar_de_silencio": 0.02,
  "tecla_de_ativacao": "delete",
  "toques_para_ativar": 3
}
```

Naturalidade offline exigiria um modelo pesado (XTTS-v2, F5-TTS) e uma GPU
NVIDIA. Sem CUDA, esses modelos levam vários segundos por frase na CPU — por
isso o Piper continua sendo a melhor opção offline em tempo real aqui.

## A voz do JARVIS nas frases fixas

As respostas que não mudam saem na **voz clonada do JARVIS**; o que muda a cada
vez continua na voz do motor escolhido.

| Sai na voz do JARVIS | Sai na voz do motor |
| --- | --- |
| "Sistema ativado" / "Sistema desativado" | respostas do Claude |
| saudações, despedida | horas, data |
| "Abrindo Dead by Daylight, senhor" | resultados de busca |
| volume, bloqueio, mensagens de erro | |

São 42 frases gravadas de antemão. Isso existe por uma limitação medida: sem
CUDA, o XTTS-v2 sintetiza a **3,9x o tempo real** nesta máquina — uma frase de
5 s leva 20 s. Inviável ao vivo, irrelevante numa gravação feita uma vez.

Para regerar (depois de instalar um jogo ou criar um comando, a lista sai do
próprio código):

```bash
..\venv-clone\Scripts\python.exe scripts\gerar_frases_jarvis.py
```

Leva uns 8 minutos. Desligue com `"usar_frases_gravadas": false`.

O ambiente da clonagem fica em `Documents\Jarvis\venv-clone`, **fora do
projeto**: o `coqui-tts` exige versões de numpy e transformers que quebrariam a
escuta do Jarvis se instaladas junto.

## Acordando o Jarvis

Por padrão ele **dorme**. Aperte `DELETE` três vezes seguidas:

```
(você aperta DELETE 3x)
Jarvis: Sistema ativado.
Você: que horas são
Jarvis: São seis e vinte e cinco, senhor.
Você: quanto está o dólar
Jarvis: … (pesquisa e responde)
(você aperta DELETE 3x de novo)
Jarvis: Sistema desativado.
```

Depois de acordar ele **continua escutando** até você desativar com a mesma
sequência. Não volta a dormir sozinho após cada resposta.

Os dois avisos são sintetizados uma única vez ao iniciar e ficam guardados
prontos, então saem no instante do atalho — sem a ida à rede, que custaria uns
quatro segundos a cada ativação. Sem voz disponível (`--mudo`, sem internet)
eles viram bipe: agudo ao ativar, grave ao desativar.

Enquanto dorme o microfone nem é aberto — nada é escutado, transcrito ou
respondido. É isto que impede o assistente de responder a conversa, TV e som de
jogo, e de queimar CPU transcrevendo barulho.

A captura de teclado é global: funciona com o jogo em primeiro plano, pelo mesmo
mecanismo do Windows que o push-to-talk do Discord.

| Configuração | Para quê |
| --- | --- |
| `ativar_por_tecla` | `false` volta ao modo antigo, respondendo a tudo que ouvir |
| `tecla_de_ativacao` | `delete`, `insert`, `pause`, `scroll_lock`, `f8`... ou um caractere |
| `toques_para_ativar` | quantos toques seguidos (padrão: 3) |
| `intervalo_entre_toques` | segundos para completar a sequência (padrão: 1.5) |
| `avisar_ativacao` | `false` desliga os avisos e ativa em silêncio |
| `aviso_ao_ativar` | o que ele fala ao acordar (padrão: "Sistema ativado.") |
| `aviso_ao_desativar` | o que ele fala ao dormir (padrão: "Sistema desativado.") |

Para testar sem o gatilho: `python -m jarvis --ouvir --sempre-escutando`.

Também existe a ativação por voz, desligada por padrão: com
`"exigir_palavra_de_ativacao": true` ele só responde a frases que contenham
"Jarvis". O reconhecimento tolera os erros de transcrição do Whisper ("Javis",
"Jarvez", "Jarbas"), mas continua sendo menos confiável que a tecla — som de
jogo e TV eventualmente produzem falsos positivos.

## Ajustando a escuta

| Configuração | Para quê |
| --- | --- |
| `modelo_de_escuta` | `base` (rápido), `small` (padrão), `medium` (preciso, lento) |
| `limiar_de_silencio` | suba se ele gravar sozinho num ambiente barulhento; desça se não ouvir você |
| `silencio_para_encerrar` | segundos de silêncio que encerram a fala (padrão: 1) |
| `falar_ao_iniciar` | anunciar "Sistemas online" ao subir (padrão: ligado) |

## Estrutura

```
jarvis/
├── __main__.py        ponto de entrada, laços de texto e de voz
├── configuracoes.py   padrões + config.local.json
├── voz.py             fala pela Edge ou pelo Piper, com reserva automática
├── ouvido.py          escuta com o faster-whisper e detector de silêncio
├── gatilho.py         acorda pelo teclado; enquanto dorme, não abre o microfone
├── cerebro.py         roteia a frase: comando local ou Claude
├── conversa.py        conversa aberta com o Claude (opcional)
├── memoria.py         embeddings em SQLite, busca em numpy (RAG)
├── maquina.py         perfila o PC e ajusta os modelos ao que ele aguenta
└── comandos/
    ├── base.py        classe Comando e normalização de texto
    ├── basicos.py     saudação, horas, data, ajuda, encerrar
    ├── jogos.py       descobre e abre jogos do Steam e da Epic
    └── sistema.py     abrir programas, volume, busca, bloquear
scripts/
├── baixar_voz.py               baixa modelos do catálogo do Piper
├── iniciar_jarvis.bat          como o Jarvis sobe (com janela, para depurar)
├── iniciar_jarvis_oculto.vbs   o mesmo, sem janela e com log — usado no boot
├── parar_jarvis.ps1            encerra o Jarvis que roda oculto
└── instalar_inicializacao.ps1  liga/desliga o início junto com o Windows
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

- [x] Abrir jogos instalados
- [x] Iniciar junto com o Windows
- [x] Acordar por atalho de teclado, em vez de responder a tudo
- [x] Busca na web com fontes no navegador
- [x] Roteador Haiku / Sonnet (conservador)
- [x] Memória local com embeddings (RAG)
- [x] TickTick (tarefas por voz)
- [x] Relatório semanal de produtividade (TickTick)
- [x] GitHub (notificações, PRs, issues)
- [ ] Lembretes e temporizadores
- [ ] Controle de música (Spotify)
