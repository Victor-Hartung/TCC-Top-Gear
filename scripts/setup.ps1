$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Instale Python 3.11 x64 e repita. Nenhuma .venv anterior sera copiada." }
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip==25.3
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar pip." }
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Falha nas dependencias; confira a mensagem acima e a conexao." }
& ".\.venv\Scripts\python.exe" python\verify_install.py --manifest
if ($LASTEXITCODE -ne 0) { throw "Instalacao incompleta." }
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path (Get-Location) 'python'
    & ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Ha testes com falha; nao inicie treino ainda." }
} finally { $env:PYTHONPATH = $previousPythonPath }
Write-Host "Instalacao e testes concluidos. Proximo: python\preflight_live.py com o BizHawk."
