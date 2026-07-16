Set-StrictMode -Version 2.0

$script:SchemaVersion = 1
$script:SensitiveKeyPattern = '(?i)(password|passwd|secret|token|credential|database[-_ ]?url|aws[-_ ]?access[-_ ]?key[-_ ]?id|github[-_ ]?pat|api[-_ ]?key|file(name|path|content)?|(^|_)path$)'
$script:SensitiveValuePattern = '(?i)(bearer\s+[a-z0-9._~-]+|sk-[a-z0-9_-]{12,}|(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://\S+|(?:DATABASE_URL|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)\s*=\s*\S+|(?:AKIA|ASIA)[A-Z0-9]{16}|github_pat_[a-z0-9_]{20,}|gh[pousr]_[a-z0-9]{20,}|AIza[a-z0-9_-]{20,}|xox[baprs]-[a-z0-9-]{10,}|eyJ[a-z0-9_-]{8,}\.eyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)'
$script:PathValuePattern = '(?i)(?:^|[\s''"(])(?:[a-z]:[\\/]|\\\\|file:/+|/(?:home|users?|var|tmp|etc)/)'
$script:FileValuePattern = '(?i)(?:^|[\s''"(])[^\\/\r\n\s''"]+\.(?:env|pem|key|pfx|p12|crt|cer|txt|md|json|ya?ml|toml|ini|csv|log|zip|pdf|docx?|xlsx?|pptx?|html?|css|js|tsx?|jsx?|py|ps1|bat|cmd)(?=$|[\s''"),.;:!?])'

function Get-VASMemoryRoot {
    param([string]$Root)

    if ($Root) { return [IO.Path]::GetFullPath($Root) }
    $local = [Environment]::GetFolderPath('LocalApplicationData')
    if (-not $local) { $local = $env:LOCALAPPDATA }
    if (-not $local) { throw 'LOCALAPPDATA 위치를 확인할 수 없습니다.' }
    return (Join-Path $local 'QUINTPACT\VAS')
}

function Get-VASMemoryPath {
    param([string]$Root)
    return (Join-Path (Get-VASMemoryRoot $Root) 'memory.json')
}

function New-VASEmptyMemoryStore {
    param([string]$RecoveredFrom)

    $store = [ordered]@{
        version = $script:SchemaVersion
        paused = $false
        updatedAt = [DateTime]::UtcNow.ToString('o')
        retention = 'until-explicit-delete'
        events = @()
    }
    if ($RecoveredFrom) { $store.recoveredFrom = $RecoveredFrom }
    return $store
}

function Save-VASMemoryStore {
    param(
        [Parameter(Mandatory = $true)]$Store,
        [string]$Root
    )

    $memoryRoot = Get-VASMemoryRoot $Root
    [IO.Directory]::CreateDirectory($memoryRoot) | Out-Null
    $path = Join-Path $memoryRoot 'memory.json'
    $temp = Join-Path $memoryRoot ('.memory-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $backup = Join-Path $memoryRoot 'memory.previous.json'
    $Store.updatedAt = [DateTime]::UtcNow.ToString('o')
    $json = $Store | ConvertTo-Json -Depth 20
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($temp, $json, $utf8)

    try {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            [IO.File]::Replace($temp, $path, $backup, $true)
        } else {
            [IO.File]::Move($temp, $path)
        }
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
    }
    return $Store
}

function Enter-VASMemoryLock {
    param([string]$Root)

    $memoryRoot = Get-VASMemoryRoot $Root
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $hash = $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($memoryRoot.ToUpperInvariant())) } finally { $hasher.Dispose() }
    $mutexId = (-join ($hash | ForEach-Object { $_.ToString('x2') })).Substring(0, 16)
    $mutex = New-Object Threading.Mutex($false, "Local\QUINTPACT.VAS.Memory.$mutexId")
    $locked = $false
    try { $locked = $mutex.WaitOne(10000) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { $mutex.Dispose(); throw 'VAS_MEMORY_BUSY' }
    return [pscustomobject]@{ mutex = $mutex; locked = $true }
}

function Exit-VASMemoryLock {
    param($Guard)
    if ($null -eq $Guard) { return }
    if ($Guard.locked) { $Guard.mutex.ReleaseMutex() }
    $Guard.mutex.Dispose()
}

function Read-VASMemoryStoreUnlocked {
    param([string]$Root)

    $memoryRoot = Get-VASMemoryRoot $Root
    [IO.Directory]::CreateDirectory($memoryRoot) | Out-Null
    $path = Join-Path $memoryRoot 'memory.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return (Save-VASMemoryStore (New-VASEmptyMemoryStore) $Root)
    }

    try {
        $raw = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
        $store = $raw | ConvertFrom-Json
        if ($null -eq $store -or $store.version -ne $script:SchemaVersion -or $null -eq $store.events) {
            throw '지원하지 않는 메모리 형식입니다.'
        }
        return $store
    } catch {
        $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
        $corruptName = "memory.corrupt-$stamp.json"
        $corruptPath = Join-Path $memoryRoot $corruptName
        Move-Item -LiteralPath $path -Destination $corruptPath -Force
        return (Save-VASMemoryStore (New-VASEmptyMemoryStore $corruptName) $Root)
    }
}

function Initialize-VASMemoryStore {
    param([string]$Root)
    $guard = Enter-VASMemoryLock $Root
    try { return (Read-VASMemoryStoreUnlocked $Root) } finally { Exit-VASMemoryLock $guard }
}

function Get-VASProperty {
    param($Object, [string]$Name, $Default = $null)

    if ($null -eq $Object) { return $Default }
    if ($Object -is [Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $Default
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

function ConvertTo-VASSafeValue {
    param($Value, [int]$Depth = 0)

    if ($Depth -gt 8) { return '[depth-limit]' }
    if ($null -eq $Value) { return $null }
    if ($Value -is [string]) {
        $text = $Value
        if ($text.Length -gt 4000) { $text = $text.Substring(0, 4000) }
        if ($text -match $script:PathValuePattern -or $text.Trim() -match $script:FileValuePattern) { return '[redacted]' }
        if ($text -match $script:SensitiveValuePattern) { return '[redacted]' }
        return $text
    }
    if ($Value -is [bool] -or $Value -is [ValueType]) { return $Value }
    if ($Value -is [Collections.IDictionary]) {
        $safe = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $name = [string]$key
            if ($name -notmatch $script:SensitiveKeyPattern) {
                $safe[$name] = ConvertTo-VASSafeValue $Value[$key] ($Depth + 1)
            }
        }
        return $safe
    }
    if ($Value -is [Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = @()
        foreach ($item in $Value) { $items += ,(ConvertTo-VASSafeValue $item ($Depth + 1)) }
        return $items
    }

    $safeObject = [ordered]@{}
    foreach ($property in $Value.PSObject.Properties) {
        if ($property.Name -notmatch $script:SensitiveKeyPattern) {
            $safeObject[$property.Name] = ConvertTo-VASSafeValue $property.Value ($Depth + 1)
        }
    }
    return $safeObject
}

function ConvertTo-VASMemoryEvent {
    param($InputObject, [string]$ExistingId)

    $type = [string](Get-VASProperty $InputObject 'type' '')
    if (-not $type -or $type.Length -gt 80 -or $type -notmatch '^[a-zA-Z0-9._-]+$') {
        throw '이벤트 type 형식이 올바르지 않습니다.'
    }
    $id = $ExistingId
    if (-not $id) { $id = [Guid]::NewGuid().ToString('N') }
    $timestamp = [string](Get-VASProperty $InputObject 'timestamp' '')
    if (-not $timestamp) { $timestamp = [DateTime]::UtcNow.ToString('o') }
    $parsed = [DateTime]::MinValue
    if (-not [DateTime]::TryParse($timestamp, [ref]$parsed)) { throw 'timestamp 형식이 올바르지 않습니다.' }

    return [ordered]@{
        v = $script:SchemaVersion
        id = $id
        type = $type
        source = ([string](Get-VASProperty $InputObject 'source' 'vas'))
        projectId = ([string](Get-VASProperty $InputObject 'projectId' ''))
        timestamp = $parsed.ToUniversalTime().ToString('o')
        payload = ConvertTo-VASSafeValue (Get-VASProperty $InputObject 'payload' ([ordered]@{}))
        feedback = ConvertTo-VASSafeValue (Get-VASProperty $InputObject 'feedback' $null)
    }
}

function Get-VASMemoryStatus {
    param([string]$Root)

    $store = Initialize-VASMemoryStore $Root
    $path = Get-VASMemoryPath $Root
    return [ordered]@{
        version = $store.version
        paused = [bool]$store.paused
        count = @($store.events).Count
        bytes = (Get-Item -LiteralPath $path).Length
        updatedAt = $store.updatedAt
        retention = 'until-explicit-delete'
        recoveredFrom = (Get-VASProperty $store 'recoveredFrom' $null)
    }
}

function Get-VASMemoryEvents {
    param([string]$Root, [string]$ProjectId, [string]$Type)

    $store = Initialize-VASMemoryStore $Root
    $events = @($store.events)
    if ($ProjectId) { $events = @($events | Where-Object { $_.projectId -eq $ProjectId }) }
    if ($Type) { $events = @($events | Where-Object { $_.type -eq $Type }) }
    return $events
}

function Add-VASMemoryEvent {
    param([Parameter(Mandatory = $true)]$InputObject, [string]$Root)

    $guard = Enter-VASMemoryLock $Root
    try {
        $store = Read-VASMemoryStoreUnlocked $Root
        if ([bool]$store.paused) { return [ordered]@{ accepted = $false; paused = $true } }
        $event = ConvertTo-VASMemoryEvent $InputObject
        $store.events = @($store.events) + @($event)
        Save-VASMemoryStore $store $Root | Out-Null
        return [ordered]@{ accepted = $true; paused = $false; event = $event }
    } finally { Exit-VASMemoryLock $guard }
}

function Set-VASMemoryEvent {
    param([Parameter(Mandatory = $true)][string]$Id, [Parameter(Mandatory = $true)]$InputObject, [string]$Root)

    $guard = Enter-VASMemoryLock $Root
    try {
        $store = Read-VASMemoryStoreUnlocked $Root
        $events = @($store.events)
        $index = -1
        for ($i = 0; $i -lt $events.Count; $i++) { if ($events[$i].id -eq $Id) { $index = $i; break } }
        if ($index -lt 0) { return $null }
        $events[$index] = ConvertTo-VASMemoryEvent $InputObject $Id
        $store.events = $events
        Save-VASMemoryStore $store $Root | Out-Null
        return $events[$index]
    } finally { Exit-VASMemoryLock $guard }
}

function Remove-VASMemoryEvent {
    param([Parameter(Mandatory = $true)][string]$Id, [string]$Root)

    $guard = Enter-VASMemoryLock $Root
    try {
        $store = Read-VASMemoryStoreUnlocked $Root
        $before = @($store.events).Count
        $store.events = @($store.events | Where-Object { $_.id -ne $Id })
        $removed = $before -ne @($store.events).Count
        if ($removed) { Save-VASMemoryStore $store $Root | Out-Null }
        return $removed
    } finally { Exit-VASMemoryLock $guard }
}

function Clear-VASMemory {
    param([string]$Root)

    $guard = Enter-VASMemoryLock $Root
    try {
        $store = Read-VASMemoryStoreUnlocked $Root
        $count = @($store.events).Count
        $store.events = @()
        Save-VASMemoryStore $store $Root | Out-Null
        return [ordered]@{ removed = $count }
    } finally { Exit-VASMemoryLock $guard }
}

function Set-VASMemoryPaused {
    param([Parameter(Mandatory = $true)][bool]$Paused, [string]$Root)

    $guard = Enter-VASMemoryLock $Root
    try {
        $store = Read-VASMemoryStoreUnlocked $Root
        $store.paused = $Paused
        Save-VASMemoryStore $store $Root | Out-Null
        return [ordered]@{ paused = $Paused }
    } finally { Exit-VASMemoryLock $guard }
}

function Export-VASMemory {
    param([string]$Root)

    $store = Initialize-VASMemoryStore $Root
    return [ordered]@{
        format = 'vas-personalization-memory'
        version = $script:SchemaVersion
        exportedAt = [DateTime]::UtcNow.ToString('o')
        paused = [bool]$store.paused
        events = @($store.events)
    }
}

function Import-VASMemory {
    param([Parameter(Mandatory = $true)]$InputObject, [ValidateSet('merge', 'replace')][string]$Mode = 'merge', [string]$Root)

    $incoming = @(Get-VASProperty $InputObject 'events' @())
    if ($incoming.Count -gt 10000) { throw '한 번에 최대 10,000개 이벤트만 가져올 수 있습니다.' }
    $guard = Enter-VASMemoryLock $Root
    try {
        $store = Read-VASMemoryStoreUnlocked $Root
        $byId = [ordered]@{}
        if ($Mode -eq 'merge') { foreach ($event in @($store.events)) { $byId[[string]$event.id] = $event } }
        foreach ($item in $incoming) {
            $requestedId = [string](Get-VASProperty $item 'id' '')
            if ($requestedId -notmatch '^[a-fA-F0-9]{32}$') { $requestedId = [Guid]::NewGuid().ToString('N') }
            $byId[$requestedId] = ConvertTo-VASMemoryEvent $item $requestedId
        }
        $store.events = @($byId.Values)
        Save-VASMemoryStore $store $Root | Out-Null
        return [ordered]@{ mode = $Mode; imported = $incoming.Count; total = @($store.events).Count }
    } finally { Exit-VASMemoryLock $guard }
}

function ConvertTo-VASSafeRagValue {
    param($Value, [int]$Depth = 0)
    if ($Depth -gt 2 -or $null -eq $Value) { return $null }
    if ($Value -is [string]) {
        $text = ($Value -replace '[\x00-\x1f\x7f]', ' ' -replace '\s+', ' ').Trim()
        $text = $text -replace '(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b', '[연락처 제외]'
        $text = $text -replace '(?i)(?:[a-z]:[\\/]|\\\\)[^\s"''<>]+', '[경로 제외]'
        $text = $text -replace '(?i)\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[a-z0-9_-]{10,}\b', '[비밀값 제외]'
        if ($text.Length -gt 3000) { $text = $text.Substring(0, 3000) }
        return $text
    }
    if ($Value -is [bool] -or $Value -is [ValueType]) { return $Value }
    if ($Value -is [Collections.IEnumerable]) {
        return @($Value | Select-Object -First 20 | ForEach-Object { ConvertTo-VASSafeRagValue $_ ($Depth + 1) })
    }
    return $null
}

function New-VASLocalProject {
    param([Parameter(Mandatory = $true)][string]$Root, [Parameter(Mandatory = $true)]$InputObject)

    foreach ($forbidden in @('path', 'target', 'source', 'root')) {
        if ($null -ne $InputObject.PSObject.Properties[$forbidden]) { throw 'VAS_PROJECT_PATH_FORBIDDEN' }
    }
    $name = ([string](Get-VASProperty $InputObject 'name' '')).Trim()
    if (-not $name -or $name.Length -gt 80 -or $name -in @('.', '..') -or
        $name -match '[<>:"/\\|?*\x00-\x1f]' -or $name -match '[. ]$') {
        throw 'VAS_PROJECT_NAME_INVALID'
    }
    $baseName = [IO.Path]::GetFileNameWithoutExtension($name)
    if ($baseName -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') { throw 'VAS_PROJECT_NAME_INVALID' }
    $brief = Get-VASProperty $InputObject 'brief' ([ordered]@{})
    if ($brief -is [string] -or $brief -is [ValueType]) { throw 'VAS_PROJECT_BRIEF_INVALID' }

    $rootPath = [IO.Path]::GetFullPath($Root)
    $workspace = Join-Path $rootPath 'workspace'
    $projectsRoot = Join-Path $workspace 'projects'
    $stateRoot = Join-Path $workspace '.vas'
    $stagingRoot = Join-Path $workspace '.staging'
    foreach ($folder in @($workspace, $projectsRoot, $stateRoot, $stagingRoot)) {
        if (Test-Path -LiteralPath $folder) {
            if ((Get-Item -LiteralPath $folder -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'VAS_PROJECT_PATH_FORBIDDEN' }
        } else { [IO.Directory]::CreateDirectory($folder) | Out-Null }
    }

    $target = [IO.Path]::GetFullPath((Join-Path $projectsRoot $name))
    if ([IO.Path]::GetDirectoryName($target) -ne [IO.Path]::GetFullPath($projectsRoot).TrimEnd('\')) { throw 'VAS_PROJECT_PATH_FORBIDDEN' }

    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $hash = $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($rootPath.ToUpperInvariant())) } finally { $hasher.Dispose() }
    $mutexId = (-join ($hash | ForEach-Object { $_.ToString('x2') })).Substring(0, 16)
    $mutex = New-Object Threading.Mutex($false, "Local\QUINTPACT.VAS.Projects.$mutexId")
    $locked = $false
    $stage = $null
    $targetCreated = $false
    try {
        try { $locked = $mutex.WaitOne(10000) } catch [Threading.AbandonedMutexException] { $locked = $true }
        if (-not $locked) { throw 'VAS_PROJECT_BUSY' }
        $registryPath = Join-Path $stateRoot 'projects.json'
        $registry = [pscustomobject]@{ version = 2; projects = @() }
        if (Test-Path -LiteralPath $registryPath -PathType Leaf) {
            try { $registry = [IO.File]::ReadAllText($registryPath, [Text.Encoding]::UTF8) | ConvertFrom-Json }
            catch { throw 'VAS_PROJECT_REGISTRY_INVALID' }
        }
        if ((Test-Path -LiteralPath $target) -or @($registry.projects | Where-Object { $_.name -eq $name -or $_.path -eq $target }).Count -gt 0) {
            throw 'VAS_PROJECT_CONFLICT'
        }

        $projectId = [Guid]::NewGuid().ToString('N')
        $stage = Join-Path $stagingRoot ("create-$projectId")
        [IO.Directory]::CreateDirectory($stage) | Out-Null
        $briefJson = $brief | ConvertTo-Json -Depth 20
        if ([Text.Encoding]::UTF8.GetByteCount($briefJson) -gt 2097152) { throw 'VAS_PROJECT_BRIEF_TOO_LARGE' }
        [IO.File]::WriteAllText((Join-Path $stage 'brief.json'), $briefJson + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
        $ragContext = [ordered]@{ schema = 1; purpose = '새 프로젝트 요구사항' }
        foreach ($key in @('problem_desc', 'reference', 'sense_vision', 'sense_audio', 'sense_text', 'sense_auto', 'data_status', 'env_web', 'env_mobile', 'env_windows', 'env_edge', 'deadline', 'budget')) {
            $safeValue = ConvertTo-VASSafeRagValue (Get-VASProperty $brief $key $null)
            if ($null -ne $safeValue -and [string]$safeValue) { $ragContext[$key] = $safeValue }
        }
        $ragJson = $ragContext | ConvertTo-Json -Depth 10
        [IO.File]::WriteAllText((Join-Path $stage 'rag-context.json'), $ragJson + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
        $readme = "# VAS 프로젝트`r`n`r`n1. brief.json에서 요구사항을 확인합니다.`r`n2. 실행·테스트 명령을 정리합니다.`r`n3. 작은 단위로 구현하고 검증합니다.`r`n4. 배포 전 비밀 파일과 생성물을 다시 확인합니다.`r`n"
        [IO.File]::WriteAllText((Join-Path $stage 'README.md'), $readme, (New-Object Text.UTF8Encoding($false)))
        $metadata = Get-VASProperty $brief '_meta' $null
        $themeTokens = Get-VASProperty $metadata 'themeTokens' $null
        if ($themeTokens -is [Collections.IDictionary] -or $themeTokens -is [pscustomobject]) {
            $tokensJson = $themeTokens | ConvertTo-Json -Depth 20
            [IO.File]::WriteAllText((Join-Path $stage 'design-tokens.json'), $tokensJson + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
        }
        [IO.Directory]::Move($stage, $target)
        $stage = $null
        $targetCreated = $true

        $now = [DateTime]::UtcNow.ToString('o')
        $project = [ordered]@{
            projectId = $projectId; name = $name; path = $target; sourceType = 'new'
            source = $null; jobId = $null; importedAt = $now; updatedAt = $now; status = 'ready'
            createIndex = $true; indexEnabled = $true; goal = 'manage'; stage = 'design'
        }
        $registry.projects = @($registry.projects) + @($project)
        $registry.version = 2
        $registryJson = $registry | ConvertTo-Json -Depth 20
        $temporary = Join-Path $stateRoot ('.projects-' + [Guid]::NewGuid().ToString('N') + '.tmp')
        [IO.File]::WriteAllText($temporary, $registryJson + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
        try {
            if (Test-Path -LiteralPath $registryPath) {
                $backup = Join-Path $stateRoot 'projects.previous.json'
                if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
                [IO.File]::Replace($temporary, $registryPath, $backup, $true)
            } else { [IO.File]::Move($temporary, $registryPath) }
        } finally {
            if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
        }
        return $project
    } catch {
        if ($targetCreated -and (Test-Path -LiteralPath $target -PathType Container)) { [IO.Directory]::Delete($target, $true) }
        throw
    } finally {
        if ($stage -and (Test-Path -LiteralPath $stage -PathType Container)) { [IO.Directory]::Delete($stage, $true) }
        if ($locked) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

Export-ModuleMember -Function Get-VASMemoryRoot, Initialize-VASMemoryStore, Get-VASMemoryStatus, Get-VASMemoryEvents, Add-VASMemoryEvent, Set-VASMemoryEvent, Remove-VASMemoryEvent, Clear-VASMemory, Set-VASMemoryPaused, Export-VASMemory, Import-VASMemory, New-VASLocalProject
