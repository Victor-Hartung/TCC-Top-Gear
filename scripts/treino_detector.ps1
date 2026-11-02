param(
    [ValidateRange(1, 100000000)][int]$Passos = 4096,
    [ValidateRange(1, 100000000)][int]$CheckpointCada = 2048,
    [string]$Retomar = '',
    [switch]$MostrarComando
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    $trainArgs = @('python\train_hermes_ppo.py', '--timesteps', "$Passos", '--checkpoint-every', "$CheckpointCada")
    if ($Retomar) { $trainArgs += @('--resume', $Retomar) }
    Write-Host "Detector integrado: $Passos passos adicionais. Exige PREFLIGHT OK compativel com o codigo atual."
    if ($Retomar) { Write-Host "Retomada: $Retomar (contrato sera conferido)" }
    else { Write-Host 'Modelo novo de 47 features; modelos antigos nao serao convertidos.' }
    if ($MostrarComando) { Write-Output (@($pythonExe) + $trainArgs) }
    else {
        & $pythonExe @trainArgs
        if ($LASTEXITCODE -ne 0) { throw 'Execucao falhou; consulte o erro e registros preservados.' }
    }
} finally { Pop-Location }
