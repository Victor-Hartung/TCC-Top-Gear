param(
    [ValidateRange(1, 100000000)][int]$Passos = 500000,
    [ValidateRange(1, 100000000)][int]$CheckpointCada = 51200,
    [string]$Retomar = 'models\hermes-ppo_20260912_173640_718500\resume_prepared\resume_4096_20260912_174433_637678.zip',
    [switch]$MostrarComando
)
& (Join-Path $PSScriptRoot 'treino_detector.ps1') -Passos $Passos -CheckpointCada $CheckpointCada -Retomar $Retomar -MostrarComando:$MostrarComando
