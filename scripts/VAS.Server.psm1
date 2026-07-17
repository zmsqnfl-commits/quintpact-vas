Set-StrictMode -Version 2.0
$memoryModule = Join-Path $PSScriptRoot 'VAS.Memory.psm1'; if (-not (Get-Command Get-VASMemoryStatus -ErrorAction SilentlyContinue)) { Import-Module $memoryModule -Force }
$projectsModule = Join-Path $PSScriptRoot 'VAS.Projects.psm1'; if (-not (Get-Command Get-VASProjectRecords -ErrorAction SilentlyContinue)) { Import-Module $projectsModule -Force }
. (Join-Path $PSScriptRoot 'VAS.Server.Handoff.ps1')
function New-VASSessionToken {
    $bytes = New-Object byte[] 32
    $rng = New-Object Security.Cryptography.RNGCryptoServiceProvider
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_'))
}
function Set-VASSecurityHeaders {
    param([Net.HttpListenerResponse]$Response, [bool]$Api = $false)
    $Response.Headers['X-Content-Type-Options'] = 'nosniff'
    $Response.Headers['X-Frame-Options'] = 'DENY'
    $Response.Headers['Referrer-Policy'] = 'same-origin'
    $Response.Headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    $Response.Headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    $Response.Headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    $Response.Headers['Cache-Control'] = if ($Api) { 'no-store' } else { 'no-cache' }
}
function Write-VASResponse {
    param(
        [Net.HttpListenerContext]$Context,
        [int]$Status = 200,
        $Data = $null,
        [string]$ContentType = 'application/json; charset=utf-8',
        [byte[]]$Bytes = $null
    )
    $response = $Context.Response
    Set-VASSecurityHeaders $response ($Context.Request.Url.AbsolutePath.StartsWith('/api/'))
    $response.StatusCode = $Status
    $response.ContentType = $ContentType
    if ($null -eq $Bytes) {
        $json = if ($null -eq $Data) { '{}' } else { $Data | ConvertTo-Json -Depth 20 -Compress }
        $Bytes = [Text.Encoding]::UTF8.GetBytes($json)
    }
    $response.ContentLength64 = $Bytes.Length
    try {
        if ($Context.Request.HttpMethod -ne 'HEAD' -and $Bytes.Length -gt 0) {
            $response.OutputStream.Write($Bytes, 0, $Bytes.Length)
        }
    } finally {
        $response.OutputStream.Close()
    }
}
function Write-VASError {
    param([Net.HttpListenerContext]$Context, [int]$Status, [string]$Message, [string]$Code = 'request_failed')
    Write-VASResponse $Context $Status ([ordered]@{ error = $Message; code = $Code })
}
function Read-VASJsonBody {
    param([Net.HttpListenerRequest]$Request, [int]$MaximumBytes = 5242880)
    if (-not $Request.HasEntityBody -or $Request.ContentLength64 -eq 0) { return [pscustomobject]@{} }; if ($Request.ContentLength64 -gt $MaximumBytes) { throw '요청 본문이 너무 큽니다.' }
    $memory = New-Object IO.MemoryStream
    $buffer = New-Object byte[] 8192
    try {
        while (($read = $Request.InputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($memory.Length + $read -gt $MaximumBytes) { throw '요청 본문이 너무 큽니다.' }
            $memory.Write($buffer, 0, $read)
        }
        if ($memory.Length -eq 0) { return [pscustomobject]@{} }
        $text = [Text.Encoding]::UTF8.GetString($memory.ToArray())
        return ($text | ConvertFrom-Json)
    } catch [ArgumentException] {
        throw 'JSON 본문 형식이 올바르지 않습니다.'
    } finally {
        $memory.Dispose()
    }
}
function Test-VASConstantTimeToken {
    param([string]$Actual, [string]$Expected)
    if ($null -eq $Actual -or $null -eq $Expected) { return $false }
    $a = [Text.Encoding]::UTF8.GetBytes($Actual)
    $b = [Text.Encoding]::UTF8.GetBytes($Expected)
    if ($a.Length -ne $b.Length) { return $false }
    $difference = 0
    for ($i = 0; $i -lt $a.Length; $i++) { $difference = $difference -bor ($a[$i] -bxor $b[$i]) }
    return $difference -eq 0
}
function Test-VASApiAccess {
    param([Net.HttpListenerRequest]$Request, $State)
    if (-not [Net.IPAddress]::IsLoopback($Request.RemoteEndPoint.Address)) { return 'loopback-only' }
    if ($Request.Headers['Host'] -ne "127.0.0.1:$($State.Port)") { return 'invalid-host' }
    if (-not (Test-VASConstantTimeToken $Request.Headers['X-VAS-Token'] $State.Token)) { return 'invalid-token' }
    $expected = $State.BaseUrl.TrimEnd('/')
    $origin = $Request.Headers['Origin']
    $referer = $Request.Headers['Referer']
    if ($origin) {
        if ($origin.TrimEnd('/') -ne $expected) { return 'cross-origin' }
    } elseif ($referer) {
        try {
            $uri = New-Object Uri -ArgumentList $referer
            if ($uri.GetLeftPart([UriPartial]::Authority).TrimEnd('/') -ne $expected) { return 'cross-origin' }
        } catch { return 'cross-origin' }
    } else {
        return 'origin-required'
    }
    return $null
}
function Get-VASContentType {
    param([string]$Extension)
    $types = @{
        '.html' = 'text/html; charset=utf-8'; '.css' = 'text/css; charset=utf-8'
        '.js' = 'text/javascript; charset=utf-8'; '.json' = 'application/json; charset=utf-8'
        '.md' = 'text/markdown; charset=utf-8'; '.txt' = 'text/plain; charset=utf-8'
        '.svg' = 'image/svg+xml'; '.png' = 'image/png'; '.jpg' = 'image/jpeg'; '.jpeg' = 'image/jpeg'
        '.gif' = 'image/gif'; '.webp' = 'image/webp'; '.ico' = 'image/x-icon'; '.woff2' = 'font/woff2'
    }
    $key = $Extension.ToLowerInvariant()
    if ($types.ContainsKey($key)) { return $types[$key] }
    return $null
}
function Resolve-VASAllowedFile {
    param([string]$RootPath, [string]$Scope, [string]$RelativePath, [bool]$TextOnly = $false)
    if ($Scope -notin @('src', 'docs')) { return $null }
    if (-not $RelativePath -or $RelativePath.IndexOf([char]0) -ge 0 -or $RelativePath -match '(^|[\\/])\.\.([\\/]|$)' -or $RelativePath -match ':') { return $null }
    $scopeRoot = [IO.Path]::GetFullPath((Join-Path $RootPath $Scope))
    if (-not (Test-Path -LiteralPath $scopeRoot -PathType Container) -or (Get-Item -LiteralPath $scopeRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $null }
    $candidate = [IO.Path]::GetFullPath((Join-Path $scopeRoot ($RelativePath -replace '/', '\')))
    $boundary = $scopeRoot.TrimEnd('\') + '\'
    if (-not $candidate.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { return $null }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $null }
    $contentType = Get-VASContentType ([IO.Path]::GetExtension($candidate))
    if (-not $contentType) { return $null }
    if ($TextOnly -and $contentType -notmatch '^(text/|application/json)') { return $null }
    $cursor = $candidate
    while ($cursor.Length -gt $scopeRoot.Length) {
        if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $null }
        $cursor = Split-Path -Parent $cursor
    }
    return [ordered]@{ path = $candidate; type = $contentType; scope = $Scope; relative = ($RelativePath -replace '\\', '/') }
}
function Import-VASMigrationModuleIfAvailable {
    if (Get-Command Select-VASProjectFolder -ErrorAction SilentlyContinue) { return $true }
    $path = Join-Path $PSScriptRoot 'VAS.Migration.psm1'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
    try { Import-Module $path -DisableNameChecking } catch { return $false }
    return [bool](Get-Command Select-VASProjectFolder -ErrorAction SilentlyContinue)
}
function Get-VASBodyProperty {
    param($Body, [string]$Name, $Default = $null)
    if ($null -eq $Body) { return $Default }
    $property = $Body.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}
function Get-VASPythonCapability {
    $unsupported = $null
    $migrationProbe = Get-Command Get-VASPythonRuntime -ErrorAction SilentlyContinue
    if ($migrationProbe) {
        try {
            $runtime = Get-VASPythonRuntime
            if (-not [bool]$runtime.available -and -not $runtime.version) { return $runtime }
            if ([bool]$runtime.available -and $runtime.version -match 'Python\s+([0-9]+)\.([0-9]+)' -and [int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 10) { return $runtime }
            if ($runtime.version) { $unsupported = [ordered]@{ available = $false; command = $runtime.command; version = $runtime.version } }
        } catch { }
    }
    $candidates = @()
    if ($env:VAS_PYTHON) { $candidates += ,@{ file = $env:VAS_PYTHON; arguments = '--version'; label = 'VAS_PYTHON' } }
    $candidates += ,@{ file = 'python.exe'; arguments = '--version'; label = 'python' }
    $candidates += ,@{ file = 'py.exe'; arguments = '-3 --version'; label = 'py -3' }
    foreach ($candidate in $candidates) {
        try {
            $command = Get-Command $candidate.file -ErrorAction Stop | Select-Object -First 1
            $start = New-Object Diagnostics.ProcessStartInfo
            $start.FileName = $command.Source
            $start.Arguments = $candidate.arguments
            $start.UseShellExecute = $false
            $start.CreateNoWindow = $true
            $start.RedirectStandardOutput = $true
            $start.RedirectStandardError = $true
            $process = New-Object Diagnostics.Process
            $process.StartInfo = $start
            if (-not $process.Start()) { continue }
            if (-not $process.WaitForExit(2500)) { $process.Kill(); $process.Dispose(); continue }
            $output = ($process.StandardOutput.ReadToEnd() + ' ' + $process.StandardError.ReadToEnd()).Trim()
            $exitCode = $process.ExitCode
            $process.Dispose()
            if ($exitCode -eq 0 -and $output -match '(Python\s+([0-9]+)\.([0-9]+)(?:\.[0-9]+)?)') {
                $version = $Matches[1]
                if ([int]$Matches[2] -eq 3 -and [int]$Matches[3] -ge 10) { return [ordered]@{ available = $true; command = $candidate.label; version = $version } }
                $unsupported = [ordered]@{ available = $false; command = $candidate.label; version = $version }
            }
        } catch { }
    }
    if ($unsupported) { return $unsupported }
    return [ordered]@{ available = $false; command = $null; version = $null }
}
function Get-VASMigrationError {
    param([string]$RawMessage)
    if ($RawMessage -match '(?i)(python|py\.exe).*(없|not found|unavailable)|CLI를 찾을 수 없습니다') {
        return [ordered]@{ status = 503; code = 'python_unavailable'; message = 'Python 3을 찾을 수 없습니다. Python을 설치한 뒤 다시 시도하세요.' }
    }
    if ($RawMessage -match '(?i)(이미 존재|already exists|충돌|conflict|destination exists|target exists)') {
        return [ordered]@{ status = 409; code = 'project_conflict'; message = '같은 이름의 프로젝트가 이미 있습니다. 다른 이름을 선택하세요.' }
    }
    if ($RawMessage -match '(?i)(해시|hash|manifest|archive|backup|검증.*실패|verify)') {
        return [ordered]@{ status = 409; code = 'migration_verification_failed'; message = '백업 또는 검증에 실패했습니다. 원본은 변경되지 않았습니다.' }
    }
    if ($RawMessage -match '(?i)(confirm|확인.*일치|confirmation)') {
        return [ordered]@{ status = 400; code = 'confirmation_mismatch'; message = '확인용 프로젝트 이름이 일치하지 않습니다.' }
    }
    if ($RawMessage -match '(?i)(selection|선택|만료|작업을 찾을 수 없|job.*not found|폴더가 존재하지)') {
        return [ordered]@{ status = 400; code = 'selection_invalid'; message = '폴더 선택 또는 작업 정보가 유효하지 않습니다. 다시 선택하세요.' }
    }
    if ($RawMessage -match '(?i)(permission|access.*denied|사용 중|locked|권한)') {
        return [ordered]@{ status = 409; code = 'project_files_unavailable'; message = '프로젝트 파일에 접근할 수 없습니다. 사용 중인 프로그램과 권한을 확인하세요.' }
    }
    return [ordered]@{ status = 400; code = 'migration_input_invalid'; message = '가져오기 입력을 확인한 뒤 다시 시도하세요.' }
}
function Invoke-VASMigrationRoute {
    param([string]$Path, [Net.HttpListenerContext]$Context, $State, $Body)
    if (-not (Import-VASMigrationModuleIfAvailable)) {
        Write-VASError $Context 503 '마이그레이션 모듈을 사용할 수 없습니다.' 'migration_unavailable'; return
    }
    $root = $State.RootPath
    try {
        if ($Path -ne '/api/folder/select') {
            $python = Get-VASPythonCapability
            if (-not [bool]$python.available -and $python.version) { Write-VASError $Context 503 'Python 3.10 이상이 필요합니다. Python을 업데이트하세요.' 'python_version_unsupported'; return }
            if (-not [bool]$python.available) { Write-VASError $Context 503 'Python 3.10 이상을 찾을 수 없습니다. Python을 설치한 뒤 다시 시도하세요.' 'python_unavailable'; return }
        }
        switch ($Path) {
            '/api/folder/select' {
                $result = Select-VASProjectFolder -Root $root -Path ([string](Get-VASBodyProperty $Body 'path' ''))
                Write-VASResponse $Context 200 ([ordered]@{ cancelled = ($null -eq $result); selection = $result })
            }
            '/api/migrations/analyze' {
                $result = Analyze-VASProject -Root $root -SelectionId ([string](Get-VASBodyProperty $Body 'selectionId' '')) -Path ([string](Get-VASBodyProperty $Body 'path' ''))
                Write-VASResponse $Context 200 $result
            }
            '/api/migrations/import' {
                $createIndex = Get-VASBodyProperty $Body 'createIndex' $false
                if ($createIndex -isnot [bool]) { Write-VASError $Context 400 'createIndex는 boolean이어야 합니다.' 'invalid_create_index'; return }
                $goal = [string](Get-VASBodyProperty $Body 'goal' 'manage')
                if ($goal -notin @('manage', 'improve', 'redesign', 'upgrade')) { Write-VASError $Context 400 '가져온 뒤 할 일을 확인하세요.' 'invalid_migration_goal'; return }
                $result = Import-VASProject -Root $root -SelectionId ([string](Get-VASBodyProperty $Body 'selectionId' '')) -Path ([string](Get-VASBodyProperty $Body 'path' '')) -ProjectName ([string](Get-VASBodyProperty $Body 'projectName' '')) -CreateIndex $createIndex -Goal $goal
                Write-VASResponse $Context 201 $result
            }
            '/api/migrations/rollback' {
                $result = Undo-VASProjectImport -Root $root -JobId ([string](Get-VASBodyProperty $Body 'jobId' ''))
                Write-VASResponse $Context 200 $result
            }
            '/api/migrations/delete-source' {
                $result = Remove-VASSourceAdvanced -Root $root -JobId ([string](Get-VASBodyProperty $Body 'jobId' '')) -Confirmation ([string](Get-VASBodyProperty $Body 'confirmation' ''))
                Write-VASResponse $Context 200 $result
            }
        }
    } catch {
        $mapped = Get-VASMigrationError $_.Exception.Message
        Write-VASError $Context $mapped.status $mapped.message $mapped.code
    }
}
function Invoke-VASApiRequest {
    param([Net.HttpListenerContext]$Context, $State)
    $request = $Context.Request
    $accessError = Test-VASApiAccess $request $State
    if ($accessError) {
        $status = if ($accessError -eq 'invalid-token') { 401 } else { 403 }
        Write-VASError $Context $status 'API 접근이 거부되었습니다.'; return
    }
    $path = $request.Url.AbsolutePath.TrimEnd('/').ToLowerInvariant()
    $method = $request.HttpMethod.ToUpperInvariant()
    $body = $null
    if ($method -in @('POST', 'PUT', 'PATCH') -and $request.HasEntityBody) { $body = Read-VASJsonBody $request }
    if ($path -eq '/api/heartbeat' -and $method -eq 'POST') {
        Write-VASResponse $Context 200 ([ordered]@{ ok = $true; serverTime = [DateTime]::UtcNow.ToString('o') }); return
    }
    if ($path -eq '/api/status' -and $method -eq 'GET') {
        $uptime = [int]([DateTime]::UtcNow - $State.StartedAt).TotalSeconds
        $python = Get-VASPythonCapability
        $migrationAvailable = [bool](Import-VASMigrationModuleIfAvailable)
        $importAvailable = $migrationAvailable -and [bool]$python.available
        $reason = if (-not $migrationAvailable) { 'migration-module-unavailable' } elseif (-not [bool]$python.available -and $python.version) { 'python-version-unsupported' } elseif (-not [bool]$python.available) { 'python-unavailable' } else { $null }
        $capabilities = [ordered]@{
            projectImport = [ordered]@{ available = $importAvailable; reason = $reason }
            python = [ordered]@{ available = [bool]$python.available; command = $python.command; version = $python.version }
        }
        Write-VASResponse $Context 200 ([ordered]@{ service = 'VAS'; version = '2.6.2'; port = $State.Port; uptimeSeconds = $uptime; capabilities = $capabilities; memory = Get-VASMemoryStatus $State.MemoryRoot }); return
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
        $mode = [string](Get-VASBodyProperty $body 'mode' 'merge')
        $data = Get-VASBodyProperty $body 'data' $body
        Write-VASResponse $Context 200 (Import-VASMemory $data $mode $State.MemoryRoot); return
    }
    if ($path -eq '/api/memory/pause' -and $method -eq 'POST') {
        $paused = Get-VASBodyProperty $body 'paused' $null
        if ($paused -isnot [bool]) { Write-VASError $Context 400 'paused는 boolean이어야 합니다.'; return }
        Write-VASResponse $Context 200 (Set-VASMemoryPaused $paused $State.MemoryRoot); return
    }
    if ($path -eq '/api/files/read' -and $method -eq 'GET') {
        $file = Resolve-VASAllowedFile $State.RootPath $request.QueryString['scope'] $request.QueryString['path'] $true
        if ($null -eq $file) { Write-VASError $Context 404 '허용된 파일을 찾을 수 없습니다.'; return }
        if ((Get-Item -LiteralPath $file.path).Length -gt 1048576) { Write-VASError $Context 413 '파일이 너무 큽니다.'; return }
        $content = [IO.File]::ReadAllText($file.path, [Text.Encoding]::UTF8)
        Write-VASResponse $Context 200 ([ordered]@{ scope = $file.scope; path = $file.relative; content = $content }); return
    }
    if ($path -eq '/api/projects' -and $method -eq 'GET') {
        $projects = @(Get-VASProjectRecords -Root $State.RootPath | ForEach-Object { [ordered]@{
            projectId = $_.projectId; name = $_.name; sourceType = $_.sourceType; status = $_.status
            goal = $_.goal; stage = $_.stage; updatedAt = $_.updatedAt; indexEnabled = [bool]$_.createIndex
        } })
        Write-VASResponse $Context 200 ([ordered]@{ projects = $projects }); return
    }
    if ($path -eq '/api/projects/create' -and $method -eq 'POST') {
        try {
            $project = New-VASLocalProject -Root $State.RootPath -InputObject $body
            $warning = $null
            if (Import-VASMigrationModuleIfAvailable) { $warning = Update-VASProjectKnowledge -Root $State.RootPath }
            Write-VASResponse $Context 201 ([ordered]@{ project = $project; warning = $warning })
        }
        catch {
            $reason = $_.Exception.Message
            if ($reason -eq 'VAS_PROJECT_CONFLICT') { Write-VASError $Context 409 '같은 이름의 프로젝트가 이미 있습니다.' 'project_conflict' }
            elseif ($reason -eq 'VAS_PROJECT_BUSY') { Write-VASError $Context 409 '다른 프로젝트 작업이 진행 중입니다. 잠시 후 다시 시도하세요.' 'project_busy' }
            elseif ($reason -eq 'VAS_PROJECT_PATH_FORBIDDEN') { Write-VASError $Context 400 '프로젝트 경로는 직접 지정할 수 없습니다.' 'project_path_forbidden' }
            elseif ($reason -eq 'VAS_PROJECT_NAME_INVALID') { Write-VASError $Context 400 '프로젝트 이름을 확인하세요.' 'project_name_invalid' }
            elseif ($reason -in @('VAS_PROJECT_BRIEF_INVALID', 'VAS_PROJECT_BRIEF_TOO_LARGE')) { Write-VASError $Context 400 '프로젝트 입력 내용이 올바르지 않거나 너무 큽니다.' 'project_brief_invalid' }
            else { Write-VASError $Context 500 '프로젝트를 만들지 못했습니다. 로컬 작업 공간을 확인하세요.' 'project_create_failed' }
        }
        return
    }
    if ($path -eq '/api/projects/open' -and $method -eq 'POST') {
        $projectId = [string](Get-VASBodyProperty $body 'projectId' '')
        $project = Get-VASProjectRecord -Root $State.RootPath -ProjectId $projectId
        if ($null -eq $project) { Write-VASError $Context 404 '프로젝트를 찾을 수 없습니다.'; return }
        try { $projectPath = Resolve-VASRegisteredProjectPath -Root $State.RootPath -Project $project }
        catch { Write-VASError $Context 403 '등록된 프로젝트 경로가 허용 범위를 벗어났습니다.'; return }
        Start-Process -FilePath 'explorer.exe' -ArgumentList @($projectPath) | Out-Null
        Write-VASResponse $Context 200 ([ordered]@{ opened = $true; projectId = $projectId }); return
    }
    if ($path -eq '/api/projects/theme' -and $method -eq 'POST') {
        $projectId = [string](Get-VASBodyProperty $body 'projectId' '')
        $theme = Get-VASBodyProperty $body 'theme' $null
        if ($null -eq $theme) { Write-VASError $Context 400 '디자인 설정을 확인하세요.' 'project_theme_invalid'; return }
        try {
            $project = Set-VASProjectTheme -Root $State.RootPath -ProjectId $projectId -Theme $theme
            $warning = $null
            if (Import-VASMigrationModuleIfAvailable) { $warning = Update-VASProjectKnowledge -Root $State.RootPath }
            Write-VASResponse $Context 200 ([ordered]@{ project = $project; warning = $warning })
        } catch {
            if ($_.Exception.Message -eq 'VAS_PROJECT_NOT_FOUND') { Write-VASError $Context 404 '프로젝트를 찾을 수 없습니다.' 'project_not_found' }
            elseif ($_.Exception.Message -eq 'VAS_PROJECT_PATH_FORBIDDEN') { Write-VASError $Context 403 '프로젝트 경로가 허용 범위를 벗어났습니다.' 'project_path_forbidden' }
            else { Write-VASError $Context 400 '디자인 설정을 저장하지 못했습니다.' 'project_theme_invalid' }
        }
        return
    }
    if ($path -eq '/api/projects/export' -and $method -eq 'POST') {
        $projectId = [string](Get-VASBodyProperty $body 'projectId' '')
        try {
            $package = Export-VASProjectHandoff -Root $State.RootPath -ProjectId $projectId
            $Context.Response.Headers['Content-Disposition'] = 'attachment; filename="VAS-2.6.2-handoff.zip"'
            Write-VASResponse $Context 200 $null 'application/zip' $package.bytes
        } catch {
            if ($_.Exception.Message -eq 'VAS_PROJECT_NOT_FOUND') { Write-VASError $Context 404 '프로젝트를 찾을 수 없습니다.' 'project_not_found' }
            else { Write-VASError $Context 500 '안전 인계 ZIP을 만들지 못했습니다.' 'project_export_failed' }
        }
        return
    }
    if ($path -eq '/api/knowledge/projects' -and $method -eq 'GET') {
        $projectId = [string]$request.QueryString['projectId']
        if ($projectId -notmatch '^[A-Za-z0-9._-]{1,100}$') { Write-VASError $Context 400 '현재 프로젝트를 먼저 선택하세요.' 'project_context_required'; return }
        if ($null -eq (Get-VASProjectRecord -Root $State.RootPath -ProjectId $projectId)) { Write-VASError $Context 404 '프로젝트를 찾을 수 없습니다.' 'project_not_found'; return }
        $entries = @()
        $knowledgePath = Join-Path $State.RootPath 'workspace\.vas\project-knowledge.json'
        if (Test-Path -LiteralPath $knowledgePath -PathType Leaf) {
            if ((Get-Item -LiteralPath $knowledgePath).Length -gt 20971520) { Write-VASError $Context 413 '지식 색인이 너무 큽니다.'; return }
            try {
                $knowledge = [IO.File]::ReadAllText($knowledgePath, [Text.Encoding]::UTF8) | ConvertFrom-Json
                if ($null -ne $knowledge.PSObject.Properties['entries']) { $entries = @($knowledge.entries | Where-Object { $_.projectId -eq $projectId }) }
            } catch { Write-VASError $Context 500 '프로젝트 지식 색인을 읽을 수 없습니다.'; return }
        }
        Write-VASResponse $Context 200 ([ordered]@{ entries = $entries }); return
    }
    if ($path -eq '/api/migrations/status' -and $method -eq 'GET') {
        if (-not (Import-VASMigrationModuleIfAvailable)) { Write-VASError $Context 503 '마이그레이션 모듈을 사용할 수 없습니다.' 'migration_unavailable'; return }
        try { Write-VASResponse $Context 200 (Get-VASMigrationStatus -Root $State.RootPath -JobId $request.QueryString['id']) }
        catch {
            $mapped = Get-VASMigrationError $_.Exception.Message
            Write-VASError $Context $mapped.status $mapped.message $mapped.code
        }
        return
    }
    if ($path -in @('/api/folder/select', '/api/migrations/analyze', '/api/migrations/import', '/api/migrations/rollback', '/api/migrations/delete-source') -and $method -eq 'POST') {
        Invoke-VASMigrationRoute $path $Context $State $body; return
    }
    if ($path -in @('/api/handoffs/preview', '/api/handoffs/export') -and $method -eq 'POST') { Invoke-VASHandoffHttpRoute $path $Context $State $body; return }
    if ($path -eq '/api/shutdown' -and $method -eq 'POST') {
        $State.Shutdown = $true
        Write-VASResponse $Context 200 ([ordered]@{ shuttingDown = $true }); return
    }
    Write-VASError $Context 404 'API 경로를 찾을 수 없습니다.'
}
function Invoke-VASStaticRequest {
    param([Net.HttpListenerContext]$Context, $State)
    $request = $Context.Request
    if ($request.HttpMethod -notin @('GET', 'HEAD')) { Write-VASError $Context 405 '읽기 전용 경로입니다.'; return }
    try {
        $rawPath = $request.RawUrl.Split('?')[0]
        $path = [Uri]::UnescapeDataString($rawPath)
    } catch { Write-VASError $Context 400 '잘못된 URL입니다.'; return }
    if ($path -match '(^|[\\/])\.\.([\\/]|$)') { Write-VASError $Context 404 '파일을 찾을 수 없습니다.'; return }
    if ($path -eq '/') { $path = '/src/vas-hub.html' }
    $parts = $path.TrimStart('/').Split('/', 2)
    if ($parts.Count -ne 2) { Write-VASError $Context 404 '파일을 찾을 수 없습니다.'; return }
    $file = Resolve-VASAllowedFile $State.RootPath $parts[0] $parts[1]
    if ($null -eq $file) { Write-VASError $Context 404 '파일을 찾을 수 없습니다.'; return }
    $bytes = [IO.File]::ReadAllBytes($file.path)
    Write-VASResponse $Context 200 $null $file.type $bytes
}
function New-VASServerState {
    param([string]$RootPath, [string]$MemoryRoot, [int]$PreferredPort = 41725, [string]$RuntimeId)
    $ports = @()
    for ($offset = 0; $offset -lt 10; $offset++) {
        $candidate = $PreferredPort + $offset
        if ($candidate -gt 0 -and $candidate -le 65535) { $ports += $candidate }
    }
    if ($ports.Count -eq 0) { throw '유효한 포트가 없습니다.' }
    foreach ($port in $ports) {
        $listener = New-Object Net.HttpListener
        $listener.Prefixes.Add("http://127.0.0.1:$port/")
        try {
            $listener.Start()
            Initialize-VASMemoryStore $MemoryRoot | Out-Null
            return [ordered]@{
                Listener = $listener; Port = $port; BaseUrl = "http://127.0.0.1:$port"
                Token = New-VASSessionToken; RootPath = [IO.Path]::GetFullPath($RootPath)
                MemoryRoot = $MemoryRoot; RuntimeId = $RuntimeId; StartedAt = [DateTime]::UtcNow
                LastActivity = [DateTime]::UtcNow; Shutdown = $false
            }
        } catch {
            $listener.Close()
        }
    }
    throw "포트 $PreferredPort 부근에서 로컬 서버를 시작할 수 없습니다."
}
function Start-VASRequestLoop {
    param($State, [int]$IdleTimeoutSeconds = 1800)
    $listener = $State.Listener
    try {
        while (-not $State.Shutdown -and $listener.IsListening) {
            $context = $null
            $pending = $listener.BeginGetContext($null, $null)
            while (-not $pending.AsyncWaitHandle.WaitOne(500)) {
                if (([DateTime]::UtcNow - $State.LastActivity).TotalSeconds -ge $IdleTimeoutSeconds) {
                    $State.Shutdown = $true
                    $listener.Stop()
                    break
                }
            }
            if ($State.Shutdown -or -not $listener.IsListening) { break }
            try {
                $context = $listener.EndGetContext($pending)
                $State.LastActivity = [DateTime]::UtcNow
                if ($context.Request.Url.AbsolutePath -eq '/health') {
                    Write-VASResponse $context 200 ([ordered]@{ service = 'VAS'; version = '2.6.2'; runtimeId = $State.RuntimeId; port = $State.Port })
                } elseif ($context.Request.Url.AbsolutePath.StartsWith('/api/')) {
                    Invoke-VASApiRequest $context $State
                } else {
                    Invoke-VASStaticRequest $context $State
                }
            } catch {
                if ($null -ne $context -and $context.Response.OutputStream.CanWrite) {
                    Write-VASError $context 500 '요청을 처리하지 못했습니다.'
                }
            }
        }
    } finally {
        if ($listener.IsListening) { $listener.Stop() }
        $listener.Close()
    }
}
Export-ModuleMember -Function New-VASServerState, Start-VASRequestLoop
