param(
    [ValidateRange(1, 100000000)][int]$Passos = 204800,
    [ValidateRange(1, 100000000)][int]$CheckpointCada = 20480,
    [string]$Retomar = '',
    [switch]$MostrarComando
)
& (Join-Path $PSScriptRoot 'treino_detector.ps1') -Passos $Passos -CheckpointCada $CheckpointCada -Retomar $Retomar -MostrarComando:$MostrarComando
