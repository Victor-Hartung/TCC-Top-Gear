param(
    [ValidateSet('Preflight','Treinar')][string]$Modo = 'Preflight',
    [ValidateRange(1,100000000)][int]$Passos = 25000,
    [ValidateRange(1,100000000)][int]$CheckpointCada = 8192,
    [int]$Seed = 5200,
    [string]$Origem = 'models\hermes-ppo_20260927_152129_971034\training_candidate_263179_steps.zip',
    [string]$Retomar = '',
    [switch]$MostrarComando
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousProfile = $env:TOPGEAR_PROFILE
Push-Location -LiteralPath $projectRoot
try {
    $env:TOPGEAR_PROFILE = 'game_profile_manual_refine.ini'
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if ($Modo -eq 'Preflight') { $pythonArgs = @('python\preflight_live.py') }
    else {
        $pythonArgs = @('python\train_hermes_ppo.py','--timesteps',"$Passos",'--checkpoint-every',"$CheckpointCada",'--seed',"$Seed")
        if ($Retomar) { $pythonArgs += @('--resume',$Retomar) }
        else { $pythonArgs += @('--refine-from',$Origem) }
        Write-Host 'Azul manual / save 2 / pesos preservados / learning_rate 0.0001. Exige preflight real deste perfil.'
        Write-Host 'Passos sao adicionais. Avalie o resultado antes de aumentar o orcamento.'
    }
    if ($MostrarComando) { Write-Output (@($pythonExe) + $pythonArgs) }
    else {
        & $pythonExe @pythonArgs
        if ($LASTEXITCODE -ne 0) { throw 'Execucao falhou; consulte os registros preservados.' }
    }
} finally {
    $env:TOPGEAR_PROFILE = $previousProfile
    Pop-Location
}
