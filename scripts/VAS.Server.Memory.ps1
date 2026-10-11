# Authenticated memory routes; storage policy failures have stable public errors.
function Invoke-VASMemoryHttpRoute {
    param([string]$path, [string]$method, $body, $Context, $State)
    $request = $Context.Request
    try {
    if ($path -eq '/api/memory/consent' -and $method -eq 'POST') {
        $consent = Get-VASBodyProperty $body 'consent' $null
        if ($consent -isnot [bool]) { Write-VASError $Context 400 'consent는 boolean이어야 합니다.'; return }
        Write-VASResponse $Context 200 (Set-VASMemoryConsent $consent $State.MemoryRoot); return
    }
    if ($path -eq '/api/memory/status' -and $method -eq 'GET') {
        Write-VASResponse $Context 200 (Get-VASMemoryStatus $State.MemoryRoot); return
    }
    if ($path -eq '/api/memory/events' -and $method -eq 'GET') {
        $events = @(Get-VASMemoryEvents $State.MemoryRoot $request.QueryString['projectId'] $request.QueryString['type'])
        Write-VASResponse $Context 200 ([ordered]@{ events = $events }); return
    }
    if ($path -eq '/api/memory/events' -and $method -eq 'POST') {
        Write-VASResponse $Context 201 (Add-VASMemoryEvent $body $State.MemoryRoot); return
    }
    if ($path -eq '/api/memory/events' -and $method -eq 'DELETE') {
        Write-VASResponse $Context 200 (Clear-VASMemory $State.MemoryRoot); return
    }
    if ($path -match '^/api/memory/events/([a-f0-9]{32})$') {
        $id = $Matches[1]
        if ($method -eq 'PUT') {
            $event = Set-VASMemoryEvent $id $body $State.MemoryRoot
            if ($null -eq $event) { Write-VASError $Context 404 '기록을 찾을 수 없습니다.' } else { Write-VASResponse $Context 200 ([ordered]@{ event = $event }) }
            return
        }
        if ($method -eq 'DELETE') {
            if (Remove-VASMemoryEvent $id $State.MemoryRoot) { Write-VASResponse $Context 200 ([ordered]@{ removed = $true }) } else { Write-VASError $Context 404 '기록을 찾을 수 없습니다.' }
            return
        }
    }
    if ($path -eq '/api/memory/export' -and $method -eq 'GET') {
        Write-VASResponse $Context 200 (Export-VASMemory $State.MemoryRoot); return
    }
    if ($path -eq '/api/memory/import' -and $method -eq 'POST') {
        $mode = 'merge'
        if ($null -ne $body -and $null -ne $body.PSObject.Properties['mode']) { $mode = $body.PSObject.Properties['mode'].Value }
        if ($mode -isnot [string] -or $mode -cnotin @('merge', 'replace')) {
            Write-VASError $Context 400 'mode는 merge 또는 replace여야 합니다.' 'invalid_memory_mode'; return
        }
        $data = Get-VASBodyProperty $body 'data' $body
        Write-VASResponse $Context 200 (Import-VASMemory $data $mode $State.MemoryRoot); return
    }
    if ($path -eq '/api/memory/pause' -and $method -eq 'POST') {
        $paused = Get-VASBodyProperty $body 'paused' $null
        if ($paused -isnot [bool]) { Write-VASError $Context 400 'paused는 boolean이어야 합니다.'; return }
        Write-VASResponse $Context 200 (Set-VASMemoryPaused $paused $State.MemoryRoot); return
    }
    Write-VASError $Context 404 '작업 기억 요청을 찾을 수 없습니다.'
    } catch {
        switch ($_.Exception.Message) {
            'VAS_MEMORY_CONSENT_REQUIRED' { Write-VASError $Context 403 '작업 기억 저장 동의가 필요합니다.' 'memory_consent_required'; return }
            'VAS_MEMORY_LIMIT_EXCEEDED' { Write-VASError $Context 413 '작업 기억 저장 한도를 초과했습니다. 기존 기록을 정리한 뒤 다시 시도해 주세요.' 'memory_limit_exceeded'; return }
            'VAS_MEMORY_HISTORY_LIMIT_EXCEEDED' { Write-VASError $Context 413 '작업 기억 복구 자료의 보관 한도를 초과했습니다. 기존 파일은 보존됩니다. 필요한 자료를 내보내거나 별도 보관한 뒤 정리해 주세요.' 'memory_history_limit_exceeded'; return }
            default { throw }
        }
    }
}
