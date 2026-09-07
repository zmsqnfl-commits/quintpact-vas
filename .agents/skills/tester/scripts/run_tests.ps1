# Explicit VAS tests check; native host permissions remain authoritative.
$ErrorActionPreference = 'Stop'
$vasCheckRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
& python (Join-Path $vasCheckRoot 'scripts/agent_checks.py') tests @args
exit $LASTEXITCODE
