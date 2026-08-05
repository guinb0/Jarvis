' Sobe o Jarvis sem janela nenhuma.
'
' É isto que a inicialização automática executa. Sem console, nada aparece na
' barra de tarefas e nada "some" quando um jogo entra em tela cheia exclusiva —
' que era o que parecia ser o Jarvis fechando sozinho.
'
' Tudo que ele imprimiria vai para jarvis.log, na raiz do projeto.
' Para encerrar:  powershell -File scripts\parar_jarvis.ps1

Option Explicit

Dim shell, fso, aspas, pastaScripts, raiz, lote, registro, comando

Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

aspas        = Chr(34)
pastaScripts = fso.GetParentFolderName(WScript.ScriptFullName)
raiz         = fso.GetParentFolderName(pastaScripts)
lote         = fso.BuildPath(pastaScripts, "iniciar_jarvis.bat")
registro     = fso.BuildPath(raiz, "jarvis.log")

' Avisa o .bat de que não há ninguém para ver um "pause" — sem isto, um erro na
' partida deixaria um cmd invisível esperando uma tecla para sempre.
shell.Environment("PROCESS")("JARVIS_OCULTO") = "1"

' Forma exigida pelo cmd quando o próprio comando contém aspas:
'   cmd /c ""programa" >> "registro" 2>&1"
comando = "cmd /c " & aspas & aspas & lote & aspas & _
          " >> " & aspas & registro & aspas & " 2>&1" & aspas

' 0 = janela oculta, False = não espera terminar.
shell.Run comando, 0, False
