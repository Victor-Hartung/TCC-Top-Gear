param([switch]$MostrarComando)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$emulatorDir = Join-Path $projectRoot 'emulator\BizHawk-2.11.1-win-x64'
$emulatorExe = Join-Path $emulatorDir 'EmuHawk.exe'
$romPath = Join-Path $projectRoot 'assets\rom\Top-Gear-USA.sfc'
$luaPath = Join-Path $projectRoot 'lua\start_blue_auto.lua'
$saveName = 'Top Gear (USA).BSNESv115+.QuickSave3.State'
$sourceSave = Join-Path $projectRoot ("assets\savestates\{0}" -f $saveName)
foreach ($requiredPath in @($emulatorExe, $romPath, $luaPath, $sourceSave)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Arquivo necessario nao encontrado: $requiredPath"
    }
}
$emulatorArgs = @(
    '--socket-ip', '127.0.0.1',
    '--socket-port', '55355',
    '--load-slot', '3',
    '--lua', ('"{0}"' -f $luaPath),
    ('"{0}"' -f $romPath)
)
if ($MostrarComando) {
    Write-Output (@($emulatorExe) + $emulatorArgs)
    return
}
$saveDirectory = Join-Path $emulatorDir 'SNES\State'
$targetSave = Join-Path $saveDirectory $saveName
New-Item -ItemType Directory -Path $saveDirectory -Force | Out-Null
if ((Test-Path -LiteralPath $targetSave) -and
    ((Get-FileHash -LiteralPath $targetSave).Hash -ne (Get-FileHash -LiteralPath $sourceSave).Hash)) {
    Copy-Item -LiteralPath $targetSave -Destination ($targetSave + '.before-blue-auto.bak') -Force
}
Copy-Item -LiteralPath $sourceSave -Destination $targetSave -Force
Write-Host 'O servidor Python precisa estar aguardando antes de abrir o emulador.'
$previousProjectRoot = $env:TOPGEAR_PROJECT_ROOT
try {
    $env:TOPGEAR_PROJECT_ROOT = $projectRoot.Replace('\', '/')
    Start-Process -FilePath $emulatorExe -WorkingDirectory $emulatorDir -ArgumentList $emulatorArgs -WindowStyle Normal
} finally {
    $env:TOPGEAR_PROJECT_ROOT = $previousProjectRoot
}
