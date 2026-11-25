param(
    [ValidateSet('Preflight','Treinar')][string]$Modo = 'Preflight',
    [ValidateRange(1,100000000)][int]$Passos = 1000000,
    [ValidateRange(1,100000000)][int]$CheckpointCada = 25000,
    [switch]$SemLogDetalhado,
    [ValidateSet('apolo','apolo-v2')][string]$Cerebro = 'apolo'
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
        $pythonArgs = @('python\train_apolo_dqn.py','--named-brain',$Cerebro,'--timesteps',"$Passos",'--checkpoint-every',"$CheckpointCada")
        if ($SemLogDetalhado) { $pythonArgs += '--no-step-log' }
        $brainPath = Join-Path $projectRoot ("models\{0}.zip" -f $Cerebro)
        if (Test-Path -LiteralPath $brainPath) {
            Write-Host "Retomada automatica do cerebro DQN fixo: $brainPath"
            Write-Host 'Pesos, otimizador, contador e replay buffer serao retomados.'
        } else {
            if ($Cerebro -eq 'apolo-v2') { throw "Copia do Apolo v2 nao encontrada: $brainPath" }
            Write-Host 'Novo cerebro DQN do zero: apolo.'
            Write-Host 'Nenhum peso ou passo do Hermes PPO sera importado.'
        }
        Write-Host 'Azul automatico / save 3 / road_v6_outcome / 61 features / 10 acoes.'
        Write-Host 'Exige PREFLIGHT OK real e atual deste perfil.'
        Write-Host ("O cerebro {0} usa uma ZIP e um replay buffer proprios." -f $Cerebro)
    }
    & $pythonExe @pythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Execucao DQN falhou; consulte status.json e preserve os registros.'
    }
} finally {
    $env:TOPGEAR_PROFILE = $previousProfile
    Pop-Location
}
