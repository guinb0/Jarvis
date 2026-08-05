@echo off
REM Sobe o Jarvis em modo de escuta. E este arquivo que a inicializacao
REM automatica do Windows chama - edite aqui para mudar como ele comeca.
REM
REM Trocar o modo e so mudar a ultima linha:
REM   --ouvir           escuta pelo microfone (padrao)
REM   (sem argumento)   conversa por texto
REM   --motor piper     voz offline, sem internet
REM
REM ATENCAO: arquivo .bat exige fim de linha CRLF. Nao salve como LF.

REM Sem isto o console usa a codepage antiga e os acentos saem embaralhados.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo O ambiente virtual nao existe. Rode:
    echo    python -m venv .venv
    echo    .venv\Scripts\activate ^&^& pip install -r requirements.txt
    if not defined JARVIS_OCULTO pause
    exit /b 1
)

title Jarvis
echo [%DATE% %TIME%] iniciando
".venv\Scripts\python.exe" -m jarvis --ouvir

REM Se cair por erro, a janela fica aberta para voce ler a mensagem. Rodando
REM oculto nao ha ninguem para ver o "pause" - ele deixaria um cmd invisivel
REM esperando uma tecla para sempre, entao ali so vale quando ha janela.
if errorlevel 1 if not defined JARVIS_OCULTO pause
