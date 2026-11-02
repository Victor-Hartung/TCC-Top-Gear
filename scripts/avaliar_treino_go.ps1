$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & ".\.venv\Scripts\python.exe" "python\avaliar_modelo.py" --model "models\hermes-ppo_20260912_105450_854879\final_10240_steps.zip" --episodes 1 --compare-accelerate --require-preflight
    if ($LASTEXITCODE -ne 0) { throw "Avaliacao falhou; consulte o erro e o JSON preservado." }
} finally {
    Pop-Location
}
