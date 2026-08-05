# Faz o Jarvis subir junto com o Windows, ou desfaz isso.
#
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_inicializacao.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_inicializacao.ps1 -Remover
#
# Usa a pasta Inicializar do seu usuario — nao precisa de administrador, e para
# desfazer basta apagar o atalho (ou rodar com -Remover).

param([switch]$Remover)

$ErrorActionPreference = 'Stop'

$raiz   = Split-Path $PSScriptRoot -Parent
$oculto = Join-Path $raiz 'scripts\iniciar_jarvis_oculto.vbs'
$pasta  = [Environment]::GetFolderPath('Startup')
$atalho = Join-Path $pasta 'Jarvis.lnk'

if ($Remover) {
    if (Test-Path $atalho) {
        Remove-Item $atalho -Force
        Write-Host '[ok] Removido. O Jarvis nao sobe mais sozinho.' -ForegroundColor Green
    } else {
        Write-Host 'Nada a remover - o atalho nao existe.' -ForegroundColor Yellow
    }
    exit 0
}

if (-not (Test-Path $oculto)) { throw "Nao achei $oculto" }

# wscript.exe roda o .vbs sem console. Assim o Jarvis nao tem janela alguma:
# nada aparece na barra de tarefas e nada "some" quando um jogo entra em tela
# cheia exclusiva — que era o que parecia ser o Jarvis fechando sozinho.
$shell = New-Object -ComObject WScript.Shell
$link  = $shell.CreateShortcut($atalho)
$link.TargetPath       = "$env:SystemRoot\System32\wscript.exe"
$link.Arguments        = """$oculto"""
$link.WorkingDirectory = $raiz
$link.Description      = 'Assistente Jarvis (escuta, sem janela)'
$link.WindowStyle      = 7
$link.Save()

Write-Host '[ok] Atalho criado em:' -ForegroundColor Green
Write-Host "     $atalho"
Write-Host ''
Write-Host 'A cada login o Jarvis sobe SEM JANELA, ja escutando o microfone.' -ForegroundColor Cyan
Write-Host 'Como nao ha janela, nada some quando um jogo entra em tela cheia.' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Para conferir agora, sem reiniciar:' -ForegroundColor Cyan
Write-Host "    Start-Process '$atalho'"
Write-Host ''
Write-Host 'Para ver o que ele esta fazendo:' -ForegroundColor Cyan
Write-Host "    Get-Content '$raiz\jarvis.log' -Tail 20 -Wait"
Write-Host ''
Write-Host 'Para encerrar (nao ha janela para fechar):' -ForegroundColor Cyan
Write-Host '    powershell -ExecutionPolicy Bypass -File scripts\parar_jarvis.ps1'
Write-Host ''
Write-Host 'Para desfazer a inicializacao automatica:' -ForegroundColor Cyan
Write-Host '    powershell -ExecutionPolicy Bypass -File scripts\instalar_inicializacao.ps1 -Remover'
Write-Host ''
Write-Host 'Em modo de escuta ele segura o microfone e usa ~1 GB de RAM com o' -ForegroundColor Yellow
Write-Host 'whisper-small carregado.' -ForegroundColor Yellow
