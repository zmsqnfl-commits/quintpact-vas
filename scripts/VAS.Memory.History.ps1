$script:MaxMemoryCorruptBytes = 16 * 1024 * 1024
$script:MaxMemoryCorruptFiles = 10
$script:MaxMemoryTempBytes = 8 * 1024 * 1024
$script:MaxMemoryTempFiles = 32
$script:MemoryTempMaxAgeHours = 24
$script:MemoryTempPattern = '^\.(?:memory|consent)-.*\.tmp$'
$script:MemoryExpiredTempPattern = '^\.(?:memory|consent)-[a-f0-9]{32}\.tmp$'
$script:MemoryCorruptPattern = '^memory\.corrupt-.*\.json$'

function Assert-VASMemoryPath {
    param([string]$Path, [string]$ExpectedType = 'File')
    try { Assert-VASLocalStatePath -Path $Path -ExpectedType $ExpectedType }
    catch { throw 'VAS_MEMORY_PATH_INVALID' }
}

function Assert-VASMemoryPaths {
    param([string]$Root)
    $directory = Get-VASMemoryRoot $Root
    foreach ($name in @('memory.json', 'memory-consent.json', 'memory.previous.json')) {
        Assert-VASMemoryPath (Join-Path $directory $name)
    }
    Get-VASMemoryHistoryItems $Root | Out-Null
}

function Get-VASMemoryHistoryItems {
    param([string]$Root)
    $directory = [IO.Path]::GetFullPath((Get-VASMemoryRoot $Root)).TrimEnd('\')
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) { return @() }
    $items = @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop | Where-Object {
        [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($_.FullName)) -eq $directory
    })
    foreach ($item in $items) {
        if ((Test-VASManagedMemoryHistoryItem $item) -or $item.Name -eq 'memory-consent.json') {
            Assert-VASMemoryPath $item.FullName
        }
    }
    return @($items | Where-Object { -not $_.PSIsContainer })
}

function Test-VASManagedMemoryHistoryItem {
    param($Item)
    return ($Item.Name -in @('memory.json', 'memory.previous.json') -or
        $Item.Name -match $script:MemoryCorruptPattern -or $Item.Name -match $script:MemoryTempPattern)
}

function Assert-VASMemoryHistoryDeletionSafe {
    param([string]$Root)
    foreach ($item in @(Get-VASMemoryHistoryItems $Root)) {
        if (Test-VASManagedMemoryHistoryItem $item) {
            Assert-VASMemoryPath $item.FullName
            # Reject already locked/inaccessible files before changing the live store.
            # Closing these probes does not promise an atomic multi-file transaction.
            $probe = [IO.File]::Open($item.FullName, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
            try { } finally { $probe.Dispose() }
        }
    }
}

function Remove-VASExpiredMemoryTemps {
    param([string]$Root)
    # Validate the complete managed inventory before deleting any expired item.
    $cutoff = [DateTime]::UtcNow.AddHours(-$script:MemoryTempMaxAgeHours)
    foreach ($item in @(Get-VASMemoryHistoryItems $Root)) {
        if ($item.Name -match $script:MemoryExpiredTempPattern -and $item.LastWriteTimeUtc -le $cutoff -and
            -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Assert-VASMemoryPath $item.FullName
            try { Remove-Item -LiteralPath $item.FullName -Force -ErrorAction Stop }
            catch [IO.IOException] { } # A locked orphan remains counted; maintenance cannot prevent opting out.
            catch [UnauthorizedAccessException] { }
            catch [System.Management.Automation.ItemNotFoundException] { }
        }
    }
}

function Clear-VASMemoryHistory {
    param([string]$Root, [string]$CurrentTemp)
    Assert-VASMemoryHistoryDeletionSafe $Root
    foreach ($item in @(Get-VASMemoryHistoryItems $Root)) {
        if ($item.FullName -ne $CurrentTemp -and ($item.Name -eq 'memory.previous.json' -or
            $item.Name -match $script:MemoryCorruptPattern -or $item.Name -match $script:MemoryTempPattern)) {
            Assert-VASMemoryPath $item.FullName
            Remove-Item -LiteralPath $item.FullName -Force -ErrorAction Stop
        }
    }
}

function Get-VASMemoryHistoryStatus {
    param([string]$Root)
    $history = [ordered]@{
        currentBytes = [long]0; backupBytes = [long]0; corruptBytes = [long]0; corruptCount = 0
        tempBytes = [long]0; tempCount = 0; totalBytes = [long]0; overLimit = $false
        unsupportedPaths = $false
        limits = [ordered]@{
            maxCurrentBytes = $script:MaxMemoryBytes; maxBackupBytes = $script:MaxMemoryBytes
            maxCorruptBytes = $script:MaxMemoryCorruptBytes; maxCorruptFiles = $script:MaxMemoryCorruptFiles
            maxTempBytes = $script:MaxMemoryTempBytes; maxTempFiles = $script:MaxMemoryTempFiles
            maxTotalBytes = 40 * 1024 * 1024; maxTransientBytes = 48 * 1024 * 1024
            tempMaxAgeHours = $script:MemoryTempMaxAgeHours
        }
    }
    foreach ($item in @(Get-VASMemoryHistoryItems $Root)) {
        if (Test-VASManagedMemoryHistoryItem $item) { Assert-VASMemoryPath $item.FullName }
        if ($item.Name -eq 'memory.json') { $history.currentBytes += $item.Length }
        elseif ($item.Name -eq 'memory.previous.json') { $history.backupBytes += $item.Length }
        elseif ($item.Name -match $script:MemoryCorruptPattern) {
            $history.corruptBytes += $item.Length; $history.corruptCount++
        } elseif ($item.Name -match $script:MemoryTempPattern) {
            $history.tempBytes += $item.Length; $history.tempCount++
        }
    }
    $history.totalBytes = $history.currentBytes + $history.backupBytes + $history.corruptBytes + $history.tempBytes
    $history.overLimit = ($history.unsupportedPaths -or $history.currentBytes -gt $script:MaxMemoryBytes -or
        $history.backupBytes -gt $script:MaxMemoryBytes -or
        $history.corruptBytes -gt $script:MaxMemoryCorruptBytes -or
        $history.corruptCount -gt $script:MaxMemoryCorruptFiles -or
        $history.tempBytes -gt $script:MaxMemoryTempBytes -or
        $history.tempCount -gt $script:MaxMemoryTempFiles -or
        $history.totalBytes -gt $history.limits.maxTotalBytes)
    return $history
}

function Assert-VASMemoryHistoryCapacity {
    param([string]$Root, [long]$AdditionalCorruptBytes = 0, [int]$AdditionalCorruptFiles = 0)
    $history = Get-VASMemoryHistoryStatus $Root
    if ($history.overLimit -or
        ($history.corruptBytes + $AdditionalCorruptBytes) -gt $script:MaxMemoryCorruptBytes -or
        ($history.corruptCount + $AdditionalCorruptFiles) -gt $script:MaxMemoryCorruptFiles) {
        throw 'VAS_MEMORY_HISTORY_LIMIT_EXCEEDED'
    }
}
