. (Join-Path $PSScriptRoot 'VAS.AgentHandoff.Core.ps1')

function Import-VASAgentHandoffModuleIfAvailable {
    if (-not (Import-VASMigrationModuleIfAvailable)) { return $false }
    return [bool](Get-Command Get-VASAgentHandoffPreview -ErrorAction SilentlyContinue)
}

function Invoke-VASHandoffHttpRoute {
    param([string]$Path, [Net.HttpListenerContext]$Context, $State, $Body)
    if (-not (Import-VASAgentHandoffModuleIfAvailable)) {
        Write-VASError $Context 503 'AI 전달팩 모듈을 사용할 수 없습니다.' 'handoff_unavailable'
        return
    }
    try {
        if ($Path -eq '/api/handoffs/preview') {
            Write-VASResponse $Context 200 (Get-VASAgentHandoffPreview -Root $State.RootPath -Body $Body)
            return
        }
        $package = Export-VASAgentHandoff -Root $State.RootPath -Body $Body
        $extension = if ($package.contentType -eq 'application/zip') { 'zip' } else { 'json' }
        $Context.Response.Headers['Content-Disposition'] = 'attachment; filename="VAS-AI-HANDOFF.' + $extension + '"'
        Write-VASResponse $Context 200 $null $package.contentType $package.bytes
    } catch {
        $mapped = Get-VASAgentHandoffError $_.Exception.Message
        Write-VASError $Context $mapped.status $mapped.message $mapped.code
    }
}
