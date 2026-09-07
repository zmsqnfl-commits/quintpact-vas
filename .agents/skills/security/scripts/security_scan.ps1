# Explicit VAS security check; native host permissions remain authoritative.
$ErrorActionPreference = 'Stop'
$vasCheckRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
& python (Join-Path $vasCheckRoot 'scripts/agent_checks.py') security @args
exit $LASTEXITCODE
