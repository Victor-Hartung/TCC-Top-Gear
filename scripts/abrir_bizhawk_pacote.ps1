param([switch]$MostrarComando)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$emulatorDir = Join-Path $projectRoot 'emulator\BizHawk-2.11.1-win-x64'
$emulatorExe = Join-Path $emulatorDir 'EmuHawk.exe'
$romPath = Join-Path $projectRoot 'assets\rom\Top-Gear-USA.sfc'
if (-not (Test-Path -LiteralPath $emulatorExe)) { throw 'Emulador nao encontrado. Este script usa o BizHawk incluido no ZIP de compartilhamento.' }
if (-not (Test-Path -LiteralPath $romPath)) { throw 'ROM do pacote nao encontrada em assets\rom.' }
$emulatorArgs = @('--socket-ip','127.0.0.1','--socket-port','55355',('"{0}"' -f $romPath))
if ($MostrarComando) { Write-Output (@($emulatorExe) + $emulatorArgs); exit }
Write-Host 'O servidor Python precisa estar aguardando antes de abrir o emulador.'
Start-Process -FilePath $emulatorExe -WorkingDirectory $emulatorDir -ArgumentList $emulatorArgs
