param(
    [ValidateRange(1, 100000000)][int]$Passos = 10240,
    [ValidateRange(1, 100000000)][int]$CheckpointCada = 2048,
    [string]$Origem = 'models\hermes-ppo_20260912_175046_376997\failed_369308_steps.zip',
    [switch]$MostrarComando
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    $trainArgs = @('python\train_hermes_ppo.py', '--timesteps', "$Passos", '--checkpoint-every', "$CheckpointCada", '--initialize-policy-from', $Origem)
    Write-Host 'Novo experimento de turbo: preserva ator; contador/critico/otimizador novos. Exige PREFLIGHT OK atual.'
    if ($MostrarComando) { Write-Output (@($pythonExe) + $trainArgs) }
    else {
        & $pythonExe @trainArgs
        if ($LASTEXITCODE -ne 0) { throw 'Execucao falhou; consulte os registros preservados.' }
    }
} finally { Pop-Location }
