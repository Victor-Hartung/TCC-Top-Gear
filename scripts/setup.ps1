$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        & py -3.11 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.11 x64 e repita.' }
    }
    & $pythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falha na instalacao das dependencias.' }
    & $pythonExe -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Confira os conflitos de dependencias informados.' }
    Write-Host 'Ambiente Python pronto. Execute o preflight com o BizHawk e o perfil azul automatico.'
} finally {
    Pop-Location
}
