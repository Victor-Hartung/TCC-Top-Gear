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
        $pythonArgs = @('python\train_ares_a2c.py','--timesteps',"$Passos",'--checkpoint-every',"$CheckpointCada")
        if ($SemLogDetalhado) { $pythonArgs += '--no-step-log' }
        $brainPath = Join-Path $projectRoot 'models\ares.zip'
        if (Test-Path -LiteralPath $brainPath) {
            Write-Host "Retomada automatica do cerebro A2C fixo: $brainPath"
            Write-Host 'Pesos, critico, otimizador e contador serao retomados; A2C coleta rollouts novos.'
        } else {
            Write-Host 'Novo cerebro A2C do zero: Ares.'
            Write-Host 'Nenhum peso ou passo do Hermes PPO/Apolo DQN sera importado.'
        }
        Write-Host 'Azul automatico / save 3 / road_v6_outcome / 61 features / 10 acoes.'
        Write-Host 'Exige PREFLIGHT OK real e atual deste perfil.'
        Write-Host 'A ZIP Ares fica separada dos arquivos hermes-ppo e apolo.'
    }
    & $pythonExe @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Execucao Ares A2C falhou; consulte status.json e preserve os registros.'
    }
} finally {
    $env:TOPGEAR_PROFILE = $previousProfile
    Pop-Location
}
