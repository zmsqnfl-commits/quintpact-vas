[CmdletBinding()]
param(
    [ValidateRange(1, 65526)][int]$Port = 41725,
    [ValidateRange(2, 86400)][int]$IdleTimeoutSeconds = 1800,
    [string]$RootPath,
    [string]$StateRoot,
    [switch]$NoBrowser,
    [switch]$Server
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

if (-not $RootPath) { $RootPath = Split-Path -Parent $PSScriptRoot }
$RootPath = [IO.Path]::GetFullPath($RootPath)

Import-Module (Join-Path $PSScriptRoot 'VAS.Memory.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'VAS.Server.psm1') -Force
$migrationModule = Join-Path $PSScriptRoot 'VAS.Migration.psm1'
if (Test-Path -LiteralPath $migrationModule -PathType Leaf) {
    try { Import-Module $migrationModule -Force -DisableNameChecking } catch { Write-Warning 'VAS migration module is unavailable.' }
}

if (-not $StateRoot) { $StateRoot = Get-VASMemoryRoot }
$StateRoot = [IO.Path]::GetFullPath($StateRoot)
[IO.Directory]::CreateDirectory($StateRoot) | Out-Null
$canonicalRoot = $RootPath.TrimEnd('\').ToUpperInvariant()
$sha256 = [Security.Cryptography.SHA256]::Create()
try { $rootHashBytes = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonicalRoot)) } finally { $sha256.Dispose() }
$rootHash = (-join ($rootHashBytes | ForEach-Object { $_.ToString('x2') })).Substring(0, 16)
$runtimeId = "2.6.1-$rootHash"
$runtimePath = Join-Path $StateRoot ("runtime-$runtimeId.json")

function Write-VASRuntimeFile {
    param($State)
    $runtime = [ordered]@{
        service = 'VAS'; version = '2.6.1'; pid = $PID; port = $State.Port
        token = $State.Token; baseUrl = $State.BaseUrl
        rootPath = $RootPath; runtimeId = $runtimeId
        startedAt = [DateTime]::UtcNow.ToString('o')
    }
    $temporary = Join-Path $StateRoot ('.runtime-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $json = $runtime | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($temporary, $json, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporary -Destination $runtimePath -Force
}

function Remove-VASOwnedRuntimeFile {
    param([string]$Token)
    if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) { return }
    try {
        $current = [IO.File]::ReadAllText($runtimePath, [Text.Encoding]::UTF8) | ConvertFrom-Json
        if ($current.token -eq $Token -and [int]$current.pid -eq $PID) {
            Remove-Item -LiteralPath $runtimePath -Force
        }
    } catch { }
}

function Get-VASLiveRuntime {
    if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) { return $null }
    try {
        $runtime = [IO.File]::ReadAllText($runtimePath, [Text.Encoding]::UTF8) | ConvertFrom-Json
        if ($runtime.service -ne 'VAS' -or $runtime.version -ne '2.6.1' -or $runtime.runtimeId -ne $runtimeId -or -not $runtime.token -or [int]$runtime.port -lt 1) { throw 'invalid runtime' }
        if ([IO.Path]::GetFullPath([string]$runtime.rootPath) -ne $RootPath) { throw 'wrong VAS root' }
        $response = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/health" -f $runtime.port) -UseBasicParsing -TimeoutSec 2
        $health = $response.Content | ConvertFrom-Json
        if ($response.StatusCode -eq 200 -and $health.service -eq 'VAS' -and $health.version -eq '2.6.1' -and $health.runtimeId -eq $runtimeId -and [int]$health.port -eq [int]$runtime.port) {
            return $runtime
        }
    } catch { }
    try { Remove-Item -LiteralPath $runtimePath -Force } catch { }
    return $null
}

function Get-VASLaunchUrl {
    param($Runtime)
    $encoded = [Uri]::EscapeDataString([string]$Runtime.token)
    return ("http://127.0.0.1:{0}/src/vas-hub.html?vasToken={1}" -f $Runtime.port, $encoded)
}

function Open-VASBrowser {
    param($Runtime)
    $url = Get-VASLaunchUrl $Runtime
    if (-not $NoBrowser) { Start-Process $url | Out-Null }
    Write-Output ("VAS_READY {0}" -f $url)
}

if ($Server) {
    $state = $null
    try {
        $state = New-VASServerState -RootPath $RootPath -MemoryRoot $StateRoot -PreferredPort $Port -RuntimeId $runtimeId
        Write-VASRuntimeFile $state
        Start-VASRequestLoop -State $state -IdleTimeoutSeconds $IdleTimeoutSeconds
        exit 0
    } catch {
        [Console]::Error.WriteLine("VAS_SERVER_ERROR: {0}" -f $_.Exception.Message)
        exit 1
    } finally {
        if ($null -ne $state) { Remove-VASOwnedRuntimeFile $state.Token }
    }
}

$mutex = New-Object Threading.Mutex($false, ("Local\QUINTPACT.VAS.Launch.$runtimeId"))
$lockTaken = $false
try {
    try { $lockTaken = $mutex.WaitOne(10000) } catch [Threading.AbandonedMutexException] { $lockTaken = $true }
    if (-not $lockTaken) { throw '다른 VAS 실행 요청이 완료되지 않았습니다.' }

    $runtime = Get-VASLiveRuntime
    if ($null -ne $runtime) {
        if ($null -ne $runtime.PSObject.Properties['rootPath'] -and
            [IO.Path]::GetFullPath([string]$runtime.rootPath) -ne $RootPath) {
            throw '다른 위치의 VAS가 이미 실행 중입니다.'
        }
        Open-VASBrowser $runtime
        exit 0
    }

    $powerShell = Join-Path $PSHOME 'powershell.exe'
    if (-not (Test-Path -LiteralPath $powerShell)) { $powerShell = 'powershell.exe' }
    $quotedScript = '"' + $PSCommandPath.Replace('"', '\"') + '"'
    $quotedRoot = '"' + $RootPath.Replace('"', '\"') + '"'
    $quotedState = '"' + $StateRoot.Replace('"', '\"') + '"'
    $arguments = @(
        '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $quotedScript,
        '-Server', '-Port', [string]$Port, '-IdleTimeoutSeconds', [string]$IdleTimeoutSeconds,
        '-RootPath', $quotedRoot, '-StateRoot', $quotedState
    )
    $worker = Start-Process -FilePath $powerShell -ArgumentList $arguments -WindowStyle Hidden -PassThru

    $deadline = [DateTime]::UtcNow.AddSeconds(12)
    do {
        Start-Sleep -Milliseconds 150
        $runtime = Get-VASLiveRuntime
        if ($null -ne $runtime) { break }
        if ($worker.HasExited) { break }
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($null -eq $runtime) {
        if (-not $worker.HasExited) { Stop-Process -Id $worker.Id -Force -ErrorAction SilentlyContinue }
        throw '로컬 서버가 제한 시간 안에 시작되지 않았습니다.'
    }
    Open-VASBrowser $runtime
    exit 0
} catch {
    [Console]::Error.WriteLine("VAS_START_ERROR: {0}" -f $_.Exception.Message)
    exit 1
} finally {
    if ($lockTaken) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
