$script:MaxMemoryEvents = 10000
$script:MaxMemoryBytes = 8 * 1024 * 1024

function Get-VASMemoryLimits {
    return @{ maxEvents = $script:MaxMemoryEvents; maxBytes = $script:MaxMemoryBytes }
}

# Consent is separate from event data so capacity cannot prevent opting out.
# These helpers run under the same memory mutex as event mutations.
function Test-VASMemoryConsent {
    param([string]$Root)
    $path = Join-Path (Get-VASMemoryRoot $Root) 'memory-consent.json'
    try {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            (Get-Item -LiteralPath $path).Length -gt 1024) { return $false }
        $settings = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json
        $value = Get-VASProperty $settings 'consent' $false
        return ((Get-VASProperty $settings 'version' 0) -eq 1 -and $value -is [bool] -and $value)
    } catch { return $false }
}

function Assert-VASMemoryConsent {
    param([string]$Root)
    if (-not (Test-VASMemoryConsent $Root)) { throw 'VAS_MEMORY_CONSENT_REQUIRED' }
}

function Assert-VASMemoryCapacity {
    param($Store, [string]$Json)
    if (@($Store.events).Count -gt $script:MaxMemoryEvents -or
        [Text.Encoding]::UTF8.GetByteCount($Json) -gt $script:MaxMemoryBytes) {
        throw 'VAS_MEMORY_LIMIT_EXCEEDED'
    }
}

function Save-VASMemoryConsentUnlocked {
    param([bool]$Consent, [string]$Root)
    $directory = Get-VASMemoryRoot $Root
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    Remove-VASExpiredMemoryTemps $Root
    $path = Join-Path $directory 'memory-consent.json'
    $temp = Join-Path $directory ('.consent-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $json = @{ version = 1; consent = $Consent } | ConvertTo-Json -Compress
    try {
        [IO.File]::WriteAllText($temp, $json, (New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            [IO.File]::Replace($temp, $path, [NullString]::Value, $true)
        } else { [IO.File]::Move($temp, $path) }
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
    }
}

function Set-VASMemoryConsent {
    param([Parameter(Mandatory = $true)][bool]$Consent, [string]$Root)
    $guard = Enter-VASMemoryLock $Root
    try {
        if ($Consent) { Read-VASMemoryStoreUnlocked $Root | Out-Null }
        Save-VASMemoryConsentUnlocked $Consent $Root
        return @{ consent = $Consent }
    } finally { Exit-VASMemoryLock $guard }
}

function Get-VASMemoryRecoveryStatus {
    param([string]$Root, [string]$Reason = 'VAS_MEMORY_LIMIT_EXCEEDED')
    $history = Get-VASMemoryHistoryStatus $Root
    return [ordered]@{
        version = $script:SchemaVersion; consent = $false; paused = $true
        count = $null; bytes = $history.currentBytes
        updatedAt = $null; retention = 'until-explicit-delete'
        recoveredFrom = $null; recoveryRequired = $true; limits = Get-VASMemoryLimits
        recoveryReason = $Reason; history = $history
    }
}
