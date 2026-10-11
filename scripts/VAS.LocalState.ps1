# State is PC-local. Inspect ancestors before their children; never resolve links.
function Assert-VASLocalStatePath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [ValidateSet('Any', 'File', 'Directory')][string]$ExpectedType = 'Any'
    )
    if ($Path -notmatch '^[a-zA-Z]:[\\/]' -or $Path.Substring(2) -match '[:*?\x00-\x1f]' -or
        $Path -match '(?:^|[\\/])[^\\/]*[. ](?:[\\/]|$)') { throw 'VAS_LOCAL_STATE_PATH_INVALID' }
    try {
        $full = [IO.Path]::GetFullPath($Path); $root = [IO.Path]::GetPathRoot($full)
        if ((New-Object IO.DriveInfo($root)).DriveType -eq [IO.DriveType]::Network) { throw 'network state' }
    }
    catch { throw 'VAS_LOCAL_STATE_PATH_INVALID' }
    $parts = @($full.Substring($root.Length).Split([char[]]'\/', [StringSplitOptions]::RemoveEmptyEntries))
    foreach ($part in $parts) {
        if ($part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') { throw 'VAS_LOCAL_STATE_PATH_INVALID' }
    }
    $current = $root
    for ($index = -1; $index -lt $parts.Count; $index++) {
        if ($index -ge 0) { $current = [IO.Path]::Combine($current, $parts[$index]) }
        try { $attributes = [IO.File]::GetAttributes($current) }
        catch [IO.FileNotFoundException] { return }
        catch [IO.DirectoryNotFoundException] { return }
        catch { throw 'VAS_LOCAL_STATE_PATH_INVALID' }
        if ($attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'VAS_LOCAL_STATE_PATH_INVALID' }
        $directory = [bool]($attributes -band [IO.FileAttributes]::Directory)
        $last = ($index -eq $parts.Count - 1)
        if ((-not $last -and -not $directory) -or
            ($last -and $ExpectedType -eq 'Directory' -and -not $directory) -or
            ($last -and $ExpectedType -eq 'File' -and $directory)) { throw 'VAS_LOCAL_STATE_PATH_INVALID' }
    }
    # These preflight checks reject existing links, not all concurrent replacements.
}
