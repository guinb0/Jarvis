# Encerra o Jarvis que esta rodando oculto.
#
#   powershell -ExecutionPolicy Bypass -File scripts\parar_jarvis.ps1
#
# Sem janela para fechar, e por aqui que se desliga. Mata so o Python deste
# projeto — outros Python da maquina nao sao tocados.

$ErrorActionPreference = 'Stop'

$raiz    = Split-Path $PSScriptRoot -Parent
$python  = Join-Path $raiz '.venv\Scripts\python.exe'

$processos = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.ExecutablePath -eq $python }

if (-not $processos) {
    Write-Host 'O Jarvis nao esta rodando.' -ForegroundColor Yellow
    exit 0
}

foreach ($p in $processos) {
    Stop-Process -Id $p.ProcessId -Force
    Write-Host "[ok] Encerrado (PID $($p.ProcessId))." -ForegroundColor Green
}

# O cmd que segura o redirecionamento para o log morre junto com o filho, mas
# quando o Python cai por erro ele pode ficar para tras.
Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" |
    Where-Object { $_.CommandLine -like '*iniciar_jarvis.bat*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
