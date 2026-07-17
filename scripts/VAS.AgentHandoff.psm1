Set-StrictMode -Version Latest
$migrationModule = Join-Path $PSScriptRoot 'VAS.Migration.psm1'
if (-not (Get-Command Resolve-VASSelection -ErrorAction SilentlyContinue)) { Import-Module $migrationModule -DisableNameChecking }
$projectsModule = Join-Path $PSScriptRoot 'VAS.Projects.psm1'
if (-not (Get-Command Get-VASProjectRecord -ErrorAction SilentlyContinue)) { Import-Module $projectsModule }
. (Join-Path $PSScriptRoot 'VAS.AgentHandoff.Core.ps1')
Export-ModuleMember -Function Get-VASAgentHandoffPreview, Export-VASAgentHandoff, Get-VASAgentHandoffError
