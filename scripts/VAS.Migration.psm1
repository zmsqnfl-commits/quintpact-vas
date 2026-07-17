Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-VASRoot {
    param([string]$Root)
    if ([string]::IsNullOrWhiteSpace($Root)) {
        return (Split-Path -Parent $PSScriptRoot)
    }
    return [IO.Path]::GetFullPath($Root)
}

function Get-VASStateRoot {
    param([string]$Root)
    $path = Join-Path (Resolve-VASRoot $Root) 'workspace\.vas'
    [IO.Directory]::CreateDirectory($path) | Out-Null
    return $path
}

function Read-VASJsonFile {
    param([string]$Path, $Default)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $Default }
    try { return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json) }
    catch { throw "상태 파일을 읽을 수 없습니다: $Path" }
}

function Write-VASJsonFile {
    param([string]$Path, $Value)
    $parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = "$Path.$([Guid]::NewGuid().ToString('N')).tmp"
    $json = $Value | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($temporary, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    try {
        if (Test-Path -LiteralPath $Path) {
            try { [IO.File]::Replace($temporary, $Path, $null) }
            catch { Move-Item -LiteralPath $temporary -Destination $Path -Force }
        } else {
            [IO.File]::Move($temporary, $Path)
        }
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Test-VASPythonCandidate {
    param([string]$File, [string[]]$Prefix, [string]$Display)
    try {
        $version = (& $File @Prefix '--version' 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $version -notmatch '^Python\s+(\d+)\.(\d+)') { return $null }
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) { return $null }
        return [pscustomobject]@{
            File = $File; Prefix = @($Prefix); Display = $Display; Version = $version
        }
    } catch { return $null }
}

function Find-VASPythonCommand {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($env:VAS_PYTHON)) {
        $configured = Get-Command -Name $env:VAS_PYTHON -ErrorAction SilentlyContinue
        if ($null -ne $configured) {
            $candidates += [pscustomobject]@{
                File = $configured.Source; Prefix = @(); Display = $env:VAS_PYTHON
            }
        }
    }
    $python = Get-Command -Name 'python' -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        $candidates += [pscustomobject]@{ File = $python.Source; Prefix = @(); Display = 'python' }
    }
    $launcher = Get-Command -Name 'py' -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        $candidates += [pscustomobject]@{ File = $launcher.Source; Prefix = @('-3'); Display = 'py' }
    }
    foreach ($candidate in $candidates) {
        $match = Test-VASPythonCandidate $candidate.File $candidate.Prefix $candidate.Display
        if ($null -ne $match) { return $match }
    }
    return $null
}

function Get-VASPythonRuntime {
    [CmdletBinding()]
    param()
    $runtime = Find-VASPythonCommand
    if ($null -eq $runtime) {
        return [pscustomobject]@{
            available = $false; command = $null; arguments = @(); version = $null
        }
    }
    return [pscustomobject]@{
        available = $true; command = $runtime.Display
        arguments = @($runtime.Prefix); version = $runtime.Version
    }
}

function Get-VASPythonCommand {
    $runtime = Find-VASPythonCommand
    if ($null -eq $runtime) {
        throw 'Python 3.10 이상을 찾을 수 없습니다. Python 3.10 이상을 설치하거나 VAS_PYTHON을 설정하세요.'
    }
    return $runtime
}

function Invoke-VASPythonUtf8 {
    param([string]$File, [string[]]$Arguments)
    $previous = [Environment]::GetEnvironmentVariable('PYTHONUTF8', 'Process')
    $previousEncoding = [Console]::OutputEncoding
    try {
        [Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'Process')
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        $output = (& $File @Arguments 2>&1 | Out-String).Trim()
        return [pscustomobject]@{ Output = $output; ExitCode = $LASTEXITCODE }
    } finally {
        [Console]::OutputEncoding = $previousEncoding
        [Environment]::SetEnvironmentVariable('PYTHONUTF8', $previous, 'Process')
    }
}

function Invoke-VASMigrationCli {
    param([string]$Root, [string[]]$Arguments)
    $vasRoot = Resolve-VASRoot $Root
    $script = Join-Path $PSScriptRoot 'vas-project-import.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw "CLI를 찾을 수 없습니다: $script" }
    $python = Get-VASPythonCommand
    $allArguments = @($script, '--root', $vasRoot) + $Arguments + @('--json')
    $invokeArguments = @($python.Prefix) + $allArguments
    $execution = Invoke-VASPythonUtf8 $python.File $invokeArguments
    $output = $execution.Output
    if ($execution.ExitCode -ne 0) {
        $message = "마이그레이션 명령 실패: $output"
        try {
            $errorResult = $output | ConvertFrom-Json
            if ($errorResult.message) { $message = $errorResult.message }
        } catch { }
        throw $message
    }
    try { return ($output | ConvertFrom-Json) }
    catch { throw "마이그레이션 응답이 올바른 JSON이 아닙니다." }
}

function Update-VASProjectKnowledge {
    param([string]$Root)
    try {
        $vasRoot = Resolve-VASRoot $Root
        $script = Join-Path $PSScriptRoot 'vas-project-knowledge.py'
        if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'missing knowledge builder' }
        $python = Get-VASPythonCommand
        $arguments = @($python.Prefix) + @($script, '--root', $vasRoot, '--json', 'build')
        $execution = Invoke-VASPythonUtf8 $python.File $arguments
        $output = $execution.Output
        if ($execution.ExitCode -ne 0) { throw 'knowledge build failed' }
        $result = $output | ConvertFrom-Json
        if ($result.status -ne 'built') { throw 'knowledge build incomplete' }
        if (@($result.warnings).Count -gt 0) { return (@($result.warnings) -join ' ') }
        return $null
    } catch {
        return '프로젝트는 등록됐지만 RAG 색인 갱신에 실패했습니다. CLI build를 다시 실행하세요.'
    }
}

function Add-VASKnowledgeWarning {
    param($Result, [string]$Warning)
    if (-not [string]::IsNullOrWhiteSpace($Warning)) {
        $Result | Add-Member -NotePropertyName warning -NotePropertyValue $Warning -Force
    }
    return $Result
}

function Save-VASSelection {
    param([string]$Root, [string]$Path)
    $stateRoot = Get-VASStateRoot $Root
    $storePath = Join-Path $stateRoot 'selections.json'
    $default = [pscustomobject]@{ version = 1; selections = @() }
    $store = Read-VASJsonFile $storePath $default
    $cutoff = [DateTimeOffset]::UtcNow.AddMinutes(-30)
    $active = @($store.selections | Where-Object {
        try { [DateTimeOffset]::Parse($_.selectedAt) -ge $cutoff } catch { $false }
    })
    $item = [pscustomobject]@{
        selectionId = [Guid]::NewGuid().ToString('N')
        path = $Path
        name = [IO.Path]::GetFileName($Path.TrimEnd('\', '/'))
        selectedAt = [DateTimeOffset]::UtcNow.ToString('o')
    }
    Write-VASJsonFile $storePath ([pscustomobject]@{ version = 1; selections = @($active + $item) })
    return $item
}

function Resolve-VASSelection {
    param([string]$Root, [string]$SelectionId, [string]$Path)
    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Container)) { throw "폴더가 존재하지 않습니다: $Path" }
        return (Get-Item -LiteralPath $Path -Force).FullName
    }
    if ([string]::IsNullOrWhiteSpace($SelectionId)) { throw 'selectionId 또는 path가 필요합니다.' }
    $storePath = Join-Path (Get-VASStateRoot $Root) 'selections.json'
    $store = Read-VASJsonFile $storePath ([pscustomobject]@{ version = 1; selections = @() })
    $item = @($store.selections | Where-Object { $_.selectionId -eq $SelectionId }) | Select-Object -First 1
    if ($null -eq $item) { throw '폴더 선택이 없거나 만료되었습니다.' }
    if ([DateTimeOffset]::Parse($item.selectedAt) -lt [DateTimeOffset]::UtcNow.AddMinutes(-30)) {
        throw '폴더 선택이 만료되었습니다. 다시 선택하세요.'
    }
    if (-not (Test-Path -LiteralPath $item.path -PathType Container)) { throw '선택한 폴더가 더 이상 존재하지 않습니다.' }
    return $item.path
}

function Convert-VASJobResult {
    param($Raw)
    return [pscustomobject]@{
        jobId = $Raw.job_id; status = $Raw.status; source = $Raw.source; target = $Raw.target
        archive = $Raw.archive; manifest = $Raw.manifest; gitBundle = $Raw.git_bundle
        idempotent = [bool]$Raw.idempotent
    }
}

function Save-VASJob {
    param([string]$Root, $Job)
    $path = Join-Path (Get-VASStateRoot $Root) "jobs\$($Job.jobId).json"
    $value = [pscustomobject]@{
        version = 1; jobId = $Job.jobId; status = $Job.status; source = $Job.source
        target = $Job.target; archive = $Job.archive; manifest = $Job.manifest
        gitBundle = $Job.gitBundle; idempotent = $Job.idempotent
        goal = if ($null -ne $Job.PSObject.Properties['goal']) { $Job.goal } else { $null }
        updatedAt = [DateTimeOffset]::UtcNow.ToString('o')
    }
    Write-VASJsonFile $path $value
    return $value
}

function Update-VASRegistry {
    param([string]$Root, $Job, [switch]$Remove, [Nullable[bool]]$CreateIndex = $null, [string]$Goal = $null)
    $path = Join-Path (Get-VASStateRoot $Root) 'projects.json'
    $store = Read-VASJsonFile $path ([pscustomobject]@{ version = 2; projects = @() })
    $existing = @($store.projects | Where-Object {
        $_.jobId -eq $Job.jobId -or $_.path -eq $Job.target
    }) | Select-Object -First 1
    $items = @($store.projects | Where-Object { $_.jobId -ne $Job.jobId -and $_.path -ne $Job.target })
    if (-not $Remove) {
        $indexEnabled = if ($null -ne $CreateIndex) {
            [bool]$CreateIndex
        } elseif ($null -ne $existing -and $null -ne $existing.PSObject.Properties['createIndex']) {
            [bool]$existing.createIndex
        } else { $false }
        $projectGoal = if ($Goal -in @('manage', 'improve', 'redesign', 'upgrade')) { $Goal } elseif ($null -ne $existing -and $null -ne $existing.PSObject.Properties['goal'] -and [string]$existing.goal -in @('manage', 'improve', 'redesign', 'upgrade')) { [string]$existing.goal } else { 'manage' }
        $projectStage = if ($projectGoal -eq 'redesign') { 'design' } elseif ($indexEnabled -or $projectGoal -in @('improve', 'upgrade')) { 'knowledge' } else { 'ready' }
        $now = [DateTimeOffset]::UtcNow.ToString('o')
        $items += [pscustomobject]@{
            projectId = $Job.jobId; name = [IO.Path]::GetFileName($Job.target); path = $Job.target
            sourceType = 'imported'; source = $Job.source; jobId = $Job.jobId
            importedAt = $now; updatedAt = $now; status = $Job.status
            createIndex = $indexEnabled; indexEnabled = $indexEnabled; goal = $projectGoal; stage = $projectStage
        }
    }
    Write-VASJsonFile $path ([pscustomobject]@{ version = 2; projects = @($items) })
}

function Select-VASProjectFolder {
    [CmdletBinding()]
    param([string]$Root, [string]$Path)
    $selected = $Path
    if ([string]::IsNullOrWhiteSpace($selected)) {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $owner = New-Object System.Windows.Forms.Form
        $dialog.Description = '원래 프로젝트가 있는 폴더를 선택하세요'
        $dialog.ShowNewFolderButton = $false
        $dialog.RootFolder = [Environment+SpecialFolder]::MyComputer
        $initialPath = Split-Path -Parent (Resolve-VASRoot $Root)
        if (Test-Path -LiteralPath $initialPath -PathType Container) {
            $dialog.SelectedPath = $initialPath
        }
        $owner.Text = 'VAS 폴더 선택'
        $owner.ShowInTaskbar = $false
        $owner.TopMost = $true
        $owner.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
        $owner.Size = New-Object System.Drawing.Size(1, 1)
        $owner.Opacity = 0
        try {
            $owner.Show()
            $owner.Activate()
            if ($dialog.ShowDialog($owner) -ne [System.Windows.Forms.DialogResult]::OK) { return $null }
            $selected = $dialog.SelectedPath
        } finally {
            $dialog.Dispose()
            $owner.Close()
            $owner.Dispose()
        }
    }
    if (-not (Test-Path -LiteralPath $selected -PathType Container)) { throw "폴더가 존재하지 않습니다: $selected" }
    $fullPath = (Get-Item -LiteralPath $selected -Force).FullName
    return (Save-VASSelection $Root $fullPath)
}

function Analyze-VASProject {
    [CmdletBinding()]
    param([string]$Root, [string]$SelectionId, [string]$Path)
    $source = Resolve-VASSelection $Root $SelectionId $Path
    $raw = Invoke-VASMigrationCli $Root @('analyze', $source)
    return [pscustomobject]@{
        schema = $raw.schema; selectionId = $SelectionId; source = $raw.source
        projectName = $raw.project_name; suggestedTarget = $raw.suggested_target
        fileCount = $raw.file_count; totalSize = $raw.total_size; stacks = @($raw.stacks)
        entrypoints = @($raw.entrypoints); extensions = $raw.extensions; git = $raw.git
        secretFiles = @($raw.secret_files); largeFiles = @($raw.large_files); skipped = @($raw.skipped)
    }
}

function Import-VASProject {
    [CmdletBinding()]
    param([string]$Root, [string]$SelectionId, [string]$Path, [string]$ProjectName,
          [bool]$CreateIndex = $false, [string]$Goal = 'manage')
    if ($Goal -notin @('manage', 'improve', 'redesign', 'upgrade')) { throw '가져온 뒤 할 일을 확인하세요.' }
    $source = Resolve-VASSelection $Root $SelectionId $Path
    $arguments = @('import', $source)
    if (-not [string]::IsNullOrWhiteSpace($ProjectName)) { $arguments += @('--name', $ProjectName) }
    $job = Convert-VASJobResult (Invoke-VASMigrationCli $Root $arguments)
    $job | Add-Member -NotePropertyName goal -NotePropertyValue $Goal -Force
    $saved = Save-VASJob $Root $job
    Update-VASRegistry $Root $job -CreateIndex $CreateIndex -Goal $Goal
    $saved | Add-Member -NotePropertyName createIndex -NotePropertyValue $CreateIndex -Force
    $project = @(Get-VASProjects -Root $Root | Where-Object { $_.jobId -eq $job.jobId }) | Select-Object -First 1
    $saved | Add-Member -NotePropertyName project -NotePropertyValue $project -Force
    return (Add-VASKnowledgeWarning $saved (Update-VASProjectKnowledge $Root))
}

function Get-VASMigrationStatus {
    [CmdletBinding()]
    param([string]$Root, [Parameter(Mandatory)][string]$JobId)
    if ($JobId -notmatch '^[A-Za-z0-9._-]+$') { throw '잘못된 작업 ID입니다.' }
    $path = Join-Path (Get-VASStateRoot $Root) "jobs\$JobId.json"
    if (-not (Test-Path -LiteralPath $path)) { throw "작업을 찾을 수 없습니다: $JobId" }
    return (Read-VASJsonFile $path $null)
}

function Undo-VASProjectImport {
    [CmdletBinding()]
    param([string]$Root, [Parameter(Mandatory)][string]$JobId)
    $job = Convert-VASJobResult (Invoke-VASMigrationCli $Root @('rollback', $JobId))
    $saved = Save-VASJob $Root $job
    Update-VASRegistry $Root $job -Remove
    return (Add-VASKnowledgeWarning $saved (Update-VASProjectKnowledge $Root))
}

function Remove-VASSourceAdvanced {
    [CmdletBinding()]
    param([string]$Root, [Parameter(Mandatory)][string]$JobId,
          [Parameter(Mandatory)][string]$Confirmation)
    $current = Get-VASMigrationStatus $Root $JobId
    $raw = Invoke-VASMigrationCli $Root @(
        'import', $current.source, '--name', ([IO.Path]::GetFileName($current.target)),
        '--delete-source', '--confirm-name', $Confirmation
    )
    $job = Convert-VASJobResult $raw
    $saved = Save-VASJob $Root $job
    Update-VASRegistry $Root $job
    return $saved
}

function Get-VASProjects {
    [CmdletBinding()]
    param([string]$Root)
    $path = Join-Path (Get-VASStateRoot $Root) 'projects.json'
    $store = Read-VASJsonFile $path ([pscustomobject]@{ version = 2; projects = @() })
    return @($store.projects)
}

Export-ModuleMember -Function @(
    'Select-VASProjectFolder', 'Analyze-VASProject', 'Import-VASProject',
    'Get-VASMigrationStatus', 'Undo-VASProjectImport',
    'Remove-VASSourceAdvanced', 'Get-VASProjects', 'Get-VASPythonRuntime',
    'Update-VASProjectKnowledge', 'Resolve-VASSelection', 'Find-VASPythonCommand',
    'Invoke-VASPythonUtf8'
)
