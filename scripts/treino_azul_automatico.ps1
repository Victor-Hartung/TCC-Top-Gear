param(
    [ValidateSet('Preflight','Treinar')][string]$Modo = 'Preflight',
    [ValidateRange(1,100000000)][int]$Passos = 10240,
    [ValidateRange(1,100000000)][int]$CheckpointCada = 2048,
    [string]$ImportarAtor = '',
    [string]$Retomar = '',
    [ValidatePattern('^[a-z0-9][a-z0-9_-]{0,63}$')][string]$Cerebro = 'hermes-ppo',
    [switch]$DoZero,
    [switch]$MostrarComando
)
$ErrorActionPreference = 'Stop'
if ($ImportarAtor -and $Retomar) { throw 'Escolha ImportarAtor OU Retomar; sao operacoes diferentes.' }
if ($DoZero -and ($ImportarAtor -or $Retomar)) { throw 'DoZero nao recebe um modelo anterior.' }
if ($Modo -eq 'Preflight' -and ($ImportarAtor -or $Retomar -or $DoZero)) { throw 'Preflight nao recebe modelos.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousProfile = $env:TOPGEAR_PROFILE
Push-Location -LiteralPath $projectRoot
try {
    $env:TOPGEAR_PROFILE = 'game_profile_blue_auto.ini'
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if ($Modo -eq 'Preflight') { $pythonArgs = @('python\preflight_live.py') }
    else {
        $pythonArgs = @('python\train_hermes_ppo.py','--timesteps',"$Passos",'--checkpoint-every',"$CheckpointCada")
        $cerebroFixo = Join-Path $projectRoot ('models\' + $Cerebro + '.zip')
        if ($Retomar) {
            $pythonArgs += @('--resume',$Retomar)
            if ($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Retomar) -eq [IO.Path]::GetFullPath($cerebroFixo)) {
                $pythonArgs += @('--named-brain',$Cerebro)
            }
        }
        elseif ($ImportarAtor) { $pythonArgs += @('--initialize-policy-from',$ImportarAtor) }
        elseif ($DoZero) { $pythonArgs += '--from-scratch' }
        else { $pythonArgs += @('--named-brain',$Cerebro) }
        Write-Host 'Azul automatico / save 3 / recompensa road_v6_outcome / GAE 0.995 / 61 features / 10 acoes.'
        Write-Host 'Exige PREFLIGHT OK real deste perfil. Modelos anteriores ficam preservados.'
        if ($Retomar) { Write-Host 'Retomada exige contrato v6 identico; conserva pesos/critico/Adam/contador.' }
        elseif ($ImportarAtor) { Write-Host 'Importacao explicita somente do ator; critico/Adam/contador novos.' }
        elseif ($DoZero) { Write-Host 'Treino separado do zero; cerebro fixo preservado.' }
        else { Write-Host ('Retomada automatica do cerebro fixo: ' + $cerebroFixo) }
    }
    if ($MostrarComando) { Write-Output (@($pythonExe) + $pythonArgs) }
    else {
        & $pythonExe @pythonArgs
        if ($LASTEXITCODE -ne 0) { throw 'Execucao falhou; consulte o relatorio e preserve os registros.' }
    }
} finally {
    $env:TOPGEAR_PROFILE = $previousProfile
    Pop-Location
}
