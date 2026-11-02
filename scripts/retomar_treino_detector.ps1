param(
    [ValidateRange(1, 100000000)][int]$Passos = 137216,
    [ValidateRange(1, 100000000)][int]$CheckpointCada = 51200,
    [string]$Retomar = 'models\hermes-ppo_20260912_175046_376997\failed_369308_steps.zip',
    [switch]$MostrarComando
)
& (Join-Path $PSScriptRoot 'treino_detector.ps1') -Passos $Passos -CheckpointCada $CheckpointCada -Retomar $Retomar -MostrarComando:$MostrarComando
