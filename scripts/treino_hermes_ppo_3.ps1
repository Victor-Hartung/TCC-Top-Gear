param(
    [ValidateSet('Preflight','Treinar')][string]$Modo = 'Preflight',
    [ValidateRange(1,100000000)][int]$Passos = 100000,
    [ValidateRange(1,100000000)][int]$CheckpointCada = 25000,
    [switch]$SemLogDetalhado
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousProfile = $env:TOPGEAR_PROFILE
Push-Location -LiteralPath $projectRoot
try {
    $env:TOPGEAR_PROFILE = 'game_profile_blue_auto.ini'
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if ($Modo -eq 'Preflight') {
        $pythonArgs = @('python\preflight_live.py')
    } else {
        $pythonArgs = @(
            'python\train_hermes_ppo_3.py',
            '--timesteps', "$Passos",
            '--checkpoint-every', "$CheckpointCada"
        )
        if ($SemLogDetalhado) { $pythonArgs += '--no-step-log' }
        $brainPath = Join-Path $projectRoot 'models\hermes-ppo-3.zip'
        if (Test-Path -LiteralPath $brainPath) {
            Write-Host "Retomada automatica do cerebro PPO fixo: $brainPath"
            Write-Host 'Ator, critico, Adam e contador serao retomados; PPO coleta um rollout novo.'
        } else {
            Write-Host 'Novo cerebro Hermes PPO 3 do zero.'
            Write-Host 'Nenhum peso ou passo dos outros Hermes, Apolo ou Ares sera importado.'
        }
        Write-Host 'Azul automatico / save 3 / road_v6_outcome / 61 features / 10 acoes.'
        Write-Host 'Exige PREFLIGHT OK real e atual deste perfil.'
        Write-Host 'A ZIP hermes-ppo-3 fica separada dos demais modelos.'
    }
    & $pythonExe @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Execucao Hermes PPO 3 falhou; consulte status.json e preserve os registros.'
    }
} finally {
    $env:TOPGEAR_PROFILE = $previousProfile
    Pop-Location
}
