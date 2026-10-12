[CmdletBinding()]
param(
    [ValidateRange(1, 65526)][int]$Port = 41725,
    [ValidateRange(2, 86400)][int]$IdleTimeoutSeconds = 1800,
    [string]$RootPath,
    [string]$StateRoot,
    [ValidatePattern('^[a-f0-9]{32}$')][string]$SessionId,
    [switch]$NoBrowser,
    [switch]$Server
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'VAS.Runtime.State.ps1')

if (-not $RootPath) { $RootPath = Split-Path -Parent $PSScriptRoot }
$RootPath = [IO.Path]::GetFullPath($RootPath)

Import-Module (Join-Path $PSScriptRoot 'VAS.Memory.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'VAS.Server.psm1') -Force
$migrationModule = Join-Path $PSScriptRoot 'VAS.Migration.psm1'
if (Test-Path -LiteralPath $migrationModule -PathType Leaf) {
    try { Import-Module $migrationModule -Force -DisableNameChecking } catch { Write-Warning 'VAS migration module is unavailable.' }
}

if (-not $StateRoot) { $StateRoot = Get-VASMemoryRoot }
try {
    Assert-VASRuntimePath -Path $StateRoot -ExpectedType Directory
    $StateRoot = [IO.Path]::GetFullPath($StateRoot)
    [IO.Directory]::CreateDirectory($StateRoot) | Out-Null
    Assert-VASRuntimePath -Path $StateRoot -ExpectedType Directory
} catch {
    [Console]::Error.WriteLine('VAS_START_ERROR: Private local state is unavailable. Use a local Windows folder without links (-StateRoot), or restore the default state location.')
    exit 1
}
$canonicalRoot = $RootPath.TrimEnd('\').ToUpperInvariant()
$sha256 = [Security.Cryptography.SHA256]::Create()
try { $rootHashBytes = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonicalRoot)) } finally { $sha256.Dispose() }
$rootHash = (-join ($rootHashBytes | ForEach-Object { $_.ToString('x2') })).Substring(0, 16)
$runtimeId = "2.10.0-$rootHash"
$runtimePath = Join-Path $StateRoot ("runtime-$runtimeId.json")

function Write-VASRuntimeFile {
    param($State)
    $runtime = [ordered]@{
        service = 'VAS'; version = '2.10.0'; pid = $PID; port = $State.Port
        token = $State.Token; baseUrl = $State.BaseUrl
        rootPath = $RootPath; runtimeId = $runtimeId
        startedAt = [DateTime]::UtcNow.ToString('o')
    }
    Save-VASRuntimeState -Path $runtimePath -Runtime $runtime
}

function Remove-VASOwnedRuntimeFile {
    param([string]$Token)
    try {
        $text = Read-VASRuntimeStateText $runtimePath
        if ($null -eq $text) { return }
        $current = $text | ConvertFrom-Json
        if ($current.token -eq $Token -and [int]$current.pid -eq $PID) {
            Remove-VASRuntimeStateFile $runtimePath
        }
    } catch { }
}

function Get-VASLiveRuntime {
    # Access/path failures are not stale state: preserve the file and stop launch.
    $text = Read-VASRuntimeStateText $runtimePath
    if ($null -eq $text) { return $null }
    try {
        $runtime = $text | ConvertFrom-Json
        if ($runtime.service -ne 'VAS' -or $runtime.version -ne '2.10.0' -or $runtime.runtimeId -ne $runtimeId -or -not $runtime.token -or [int]$runtime.port -lt 1 -or [int]$runtime.port -gt 65535) { throw 'invalid runtime' }
        if ([IO.Path]::GetFullPath([string]$runtime.rootPath) -ne $RootPath) { throw 'wrong VAS root' }
        $response = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/health" -f $runtime.port) -UseBasicParsing -TimeoutSec 2
        $health = $response.Content | ConvertFrom-Json
        if ($response.StatusCode -eq 200 -and $health.service -eq 'VAS' -and $health.version -eq '2.10.0' -and $health.runtimeId -eq $runtimeId -and [int]$health.port -eq [int]$runtime.port) {
            return $runtime
        }
    } catch { }
    # A new server atomically replaces stale state only after private creation succeeds.
    return $null
}

function Get-VASLaunchUrl {
    param($Runtime, [switch]$Authenticated)
    $page = '/src/vas-hub.html'
    $query = @()
    if ($SessionId) { $page = '/src/design-controller.html'; $query += 'session=' + $SessionId }
    if ($Authenticated) { $query += 'vasToken=' + [Uri]::EscapeDataString([string]$Runtime.token) }
    $url = "http://127.0.0.1:{0}{1}" -f $Runtime.port, $page
    if ($query.Count -gt 0) { $url += '?' + ($query -join '&') }
    return $url
}

function Open-VASBrowser {
    param($Runtime)
    if (-not $NoBrowser) {
        try { Start-Process (Get-VASLaunchUrl $Runtime -Authenticated) | Out-Null }
        catch { throw 'VAS browser launch failed. Retry the launcher to open the authenticated local page.' }
    }
    Write-Output ("VAS_READY {0}" -f (Get-VASLaunchUrl $Runtime))
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

    $probe = Join-Path $StateRoot ('.runtime-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $probeStream = New-VASRuntimeSecureStream $probe
    try { $probeStream.Dispose() } finally { Remove-VASRuntimeStateFile $probe }

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
