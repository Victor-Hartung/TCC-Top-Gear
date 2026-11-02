param(
    [ValidateSet('Preflight','Treinar')][string]$Modo = 'Preflight',
    [ValidateRange(1,100000000)][int]$Passos = 500000,
    [ValidateRange(1,100000000)][int]$CheckpointCada = 25000,
    [string]$Retomar = '',
    [switch]$MostrarComando
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousProfile = $env:TOPGEAR_PROFILE
Push-Location -LiteralPath $projectRoot
try {
    $env:TOPGEAR_PROFILE = 'game_profile_manual.ini'
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if ($Modo -eq 'Preflight') { $pythonArgs = @('python\preflight_live.py') }
    else {
        $pythonArgs = @('python\train_hermes_ppo.py','--timesteps',"$Passos",'--checkpoint-every',"$CheckpointCada")
        if ($Retomar) { $pythonArgs += @('--resume',$Retomar) }
        else { $pythonArgs += '--from-scratch' }
        Write-Host 'Azul manual / save 2 / 63 features / 30 acoes. Exige PREFLIGHT OK manual atual.'
        if (-not $Retomar) { Write-Host 'PPO novo; modelos anteriores preservados.' }
    }
    if ($MostrarComando) { Write-Output (@($pythonExe) + $pythonArgs) }
    else {
        & $pythonExe @pythonArgs
        if ($LASTEXITCODE -ne 0) { throw 'Execucao falhou; registros e modelos foram preservados.' }
    }
} finally {
    $env:TOPGEAR_PROFILE = $previousProfile
    Pop-Location
}
