Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-VASProjectValue {
    param($Object, [string]$Name, $Default = $null)
    if ($null -eq $Object) { return $Default }
    if ($Object -is [Collections.IDictionary]) {
        return $(if ($Object.Contains($Name)) { $Object[$Name] } else { $Default })
    }
    $property = $Object.PSObject.Properties[$Name]
    return $(if ($null -ne $property) { $property.Value } else { $Default })
}

function Get-VASProjectStatePath {
    param([Parameter(Mandatory)][string]$Root)
    $state = Join-Path ([IO.Path]::GetFullPath($Root)) 'workspace\.vas'
    [IO.Directory]::CreateDirectory($state) | Out-Null
    return (Join-Path $state 'projects.json')
}

function Write-VASProjectJson {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Value)
    $parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = Join-Path $parent ('.' + [IO.Path]::GetFileName($Path) + '-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $json = $Value | ConvertTo-Json -Depth 24
    [IO.File]::WriteAllText($temporary, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    try {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            try { [IO.File]::Replace($temporary, $Path, $null, $true) }
            catch { Move-Item -LiteralPath $temporary -Destination $Path -Force }
        } else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Get-VASDerivedStage {
    param($Record)
    $stage = [string](Get-VASProjectValue $Record 'stage' '')
    if ($stage -in @('design', 'knowledge', 'ready')) { return $stage }
    $sourceType = [string](Get-VASProjectValue $Record 'sourceType' 'new')
    $goal = [string](Get-VASProjectValue $Record 'goal' 'manage')
    if ($sourceType -eq 'new' -or $goal -eq 'redesign') { return 'design' }
    if ([bool](Get-VASProjectValue $Record 'createIndex' $false) -or $goal -in @('improve', 'upgrade')) { return 'knowledge' }
    return 'ready'
}

function ConvertTo-VASProjectRecord {
    param($Record)
    $sourceType = [string](Get-VASProjectValue $Record 'sourceType' 'new')
    if ($sourceType -notin @('new', 'imported')) { $sourceType = 'new' }
    $goal = [string](Get-VASProjectValue $Record 'goal' 'manage')
    if ($goal -notin @('manage', 'improve', 'redesign', 'upgrade')) { $goal = 'manage' }
    $createdAt = [string](Get-VASProjectValue $Record 'importedAt' '')
    if (-not $createdAt) { $createdAt = [DateTime]::UtcNow.ToString('o') }
    $updatedAt = [string](Get-VASProjectValue $Record 'updatedAt' $createdAt)
    $createIndex = [bool](Get-VASProjectValue $Record 'createIndex' $false)
    return [ordered]@{
        projectId = [string](Get-VASProjectValue $Record 'projectId' (Get-VASProjectValue $Record 'jobId' ''))
        name = [string](Get-VASProjectValue $Record 'name' '')
        path = [string](Get-VASProjectValue $Record 'path' '')
        sourceType = $sourceType
        source = Get-VASProjectValue $Record 'source' $null
        jobId = Get-VASProjectValue $Record 'jobId' $null
        importedAt = $createdAt
        updatedAt = $updatedAt
        status = [string](Get-VASProjectValue $Record 'status' 'ready')
        createIndex = $createIndex
        indexEnabled = $createIndex
        goal = $goal
        stage = Get-VASDerivedStage $Record
    }
}

function Read-VASProjectRegistry {
    param([Parameter(Mandatory)][string]$Root)
    $path = Get-VASProjectStatePath $Root
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [ordered]@{ version = 2; projects = @() }
    }
    try { $raw = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json }
    catch { throw 'VAS_PROJECT_REGISTRY_INVALID' }
    $records = if ($null -ne $raw.PSObject.Properties['projects']) { @($raw.projects) } else { @() }
    return [ordered]@{ version = 2; projects = @($records | ForEach-Object { ConvertTo-VASProjectRecord $_ }) }
}

function Save-VASProjectRegistry {
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)]$Registry)
    $Registry.version = 2
    Write-VASProjectJson (Get-VASProjectStatePath $Root) $Registry
}

function Get-VASProjectRecords {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root)
    return @((Read-VASProjectRegistry $Root).projects)
}

function Get-VASProjectRecord {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)][string]$ProjectId)
    if ($ProjectId -notmatch '^[A-Za-z0-9._-]{1,100}$') { return $null }
    return @(Get-VASProjectRecords $Root | Where-Object { $_.projectId -eq $ProjectId }) | Select-Object -First 1
}

function Resolve-VASRegisteredProjectPath {
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)]$Project)
    $projectsRoot = [IO.Path]::GetFullPath((Join-Path $Root 'workspace\projects')).TrimEnd('\')
    $path = [IO.Path]::GetFullPath([string]$Project.path).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($path) -ne $projectsRoot) { throw 'VAS_PROJECT_PATH_FORBIDDEN' }
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw 'VAS_PROJECT_NOT_FOUND' }
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'VAS_PROJECT_PATH_FORBIDDEN' }
    return $path
}

function Set-VASProjectTheme {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)][string]$ProjectId,
          [Parameter(Mandatory)]$Theme)
    $registry = Read-VASProjectRegistry $Root
    $project = @($registry.projects | Where-Object { $_.projectId -eq $ProjectId }) | Select-Object -First 1
    if ($null -eq $project) { throw 'VAS_PROJECT_NOT_FOUND' }
    $path = Resolve-VASRegisteredProjectPath $Root $project
    $json = $Theme | ConvertTo-Json -Depth 20
    if ([Text.Encoding]::UTF8.GetByteCount($json) -gt 131072) { throw 'VAS_PROJECT_THEME_TOO_LARGE' }
    try { $null = $json | ConvertFrom-Json }
    catch { throw 'VAS_PROJECT_THEME_INVALID' }
    Write-VASProjectJson (Join-Path $path 'design-tokens.json') $Theme
    $now = [DateTime]::UtcNow.ToString('o')
    $updated = @()
    foreach ($item in @($registry.projects)) {
        if ($item.projectId -eq $ProjectId) {
            $item.stage = 'knowledge'
            $item.updatedAt = $now
            $item.createIndex = $true
            $item.indexEnabled = $true
            $project = $item
        }
        $updated += $item
    }
    $registry.projects = $updated
    Save-VASProjectRegistry $Root $registry
    return $project
}

function Get-VASSafeRagMetadata {
    param([string]$Root, [string]$ProjectId)
    $path = Join-Path $Root 'workspace\.vas\project-knowledge.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return @() }
    if ((Get-Item -LiteralPath $path).Length -gt 20971520) { return @() }
    try { $index = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json }
    catch { return @() }
    $entries = if ($null -ne $index.PSObject.Properties['entries']) { @($index.entries) } else { @() }
    return @($entries | Where-Object { $_.projectId -eq $ProjectId } | Select-Object -First 500 | ForEach-Object {
        [ordered]@{
            title = [string]$_.title
            source = [string]$_.source
            line = [int]$_.line
            keywords = @($_.keywords | Select-Object -First 24)
        }
    })
}

function Get-VASFileSha256 {
    param([string]$Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { return (-join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') })) }
        finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}

function Export-VASProjectHandoff {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)][string]$ProjectId)
    $project = Get-VASProjectRecord $Root $ProjectId
    if ($null -eq $project) { throw 'VAS_PROJECT_NOT_FOUND' }
    $path = Resolve-VASRegisteredProjectPath $Root $project
    $temporary = Join-Path ([IO.Path]::GetTempPath()) ('vas-handoff-' + [Guid]::NewGuid().ToString('N'))
    $content = Join-Path $temporary 'handoff'
    [IO.Directory]::CreateDirectory($content) | Out-Null
    try {
        $summary = [ordered]@{
            schema = 1; vasVersion = '2.6.1'; projectId = $project.projectId
            name = $project.name; sourceType = $project.sourceType; goal = $project.goal
            stage = $project.stage; exportedAt = [DateTime]::UtcNow.ToString('o')
        }
        Write-VASProjectJson (Join-Path $content 'project.json') $summary
        $safeRequirements = Join-Path $path 'rag-context.json'
        if (Test-Path -LiteralPath $safeRequirements -PathType Leaf) {
            Copy-Item -LiteralPath $safeRequirements -Destination (Join-Path $content 'requirements.json')
        } else { Write-VASProjectJson (Join-Path $content 'requirements.json') ([ordered]@{ note = '공유 가능한 요구사항이 없습니다.' }) }
        $tokens = Join-Path $path 'design-tokens.json'
        if (Test-Path -LiteralPath $tokens -PathType Leaf) {
            Copy-Item -LiteralPath $tokens -Destination (Join-Path $content 'design-tokens.json')
        } else { Write-VASProjectJson (Join-Path $content 'design-tokens.json') ([ordered]@{}) }
        Write-VASProjectJson (Join-Path $content 'rag-context.json') ([ordered]@{
            projectId = $project.projectId; entries = @(Get-VASSafeRagMetadata $Root $ProjectId)
        })
        $readme = @"
# VAS 안전 인계본

이 ZIP에는 프로젝트 원본 소스, 환경 변수, 절대 경로, API 키, 개인화 기록이 없습니다.

1. `project.json`에서 프로젝트 상태를 확인합니다.
2. `requirements.json`과 `design-tokens.json`을 검토합니다.
3. `rag-context.json`은 제목·키워드·상대 경로만 포함합니다.
4. `SHA256SUMS.txt`로 파일 무결성을 확인합니다.
"@
        [IO.File]::WriteAllText((Join-Path $content 'README.md'), $readme.Trim() + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
        $lines = Get-ChildItem -LiteralPath $content -File | Sort-Object Name | ForEach-Object {
            (Get-VASFileSha256 $_.FullName) + '  ' + $_.Name
        }
        [IO.File]::WriteAllLines((Join-Path $content 'SHA256SUMS.txt'), $lines, [Text.UTF8Encoding]::new($false))
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = Join-Path $temporary 'handoff.zip'
        [IO.Compression.ZipFile]::CreateFromDirectory($content, $zip, [IO.Compression.CompressionLevel]::Optimal, $false)
        $safeName = ([string]$project.name -replace '[^A-Za-z0-9가-힣._-]', '-').Trim('-')
        if (-not $safeName) { $safeName = 'vas-project' }
        return [ordered]@{ fileName = $safeName + '-VAS-2.6.1-handoff.zip'; bytes = [IO.File]::ReadAllBytes($zip) }
    } finally {
        if (Test-Path -LiteralPath $temporary -PathType Container) { [IO.Directory]::Delete($temporary, $true) }
    }
}

Export-ModuleMember -Function @(
    'Get-VASProjectRecords', 'Get-VASProjectRecord', 'Set-VASProjectTheme',
    'Export-VASProjectHandoff', 'Resolve-VASRegisteredProjectPath'
)
