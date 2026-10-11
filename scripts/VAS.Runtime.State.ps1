# Runtime tokens are local bearer credentials. File ACLs isolate other Windows
# users; they do not protect against the same user, administrators, or malware.
. (Join-Path $PSScriptRoot 'VAS.LocalState.ps1')

function Get-VASRuntimePrincipals {
    return @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value, 'S-1-5-18', 'S-1-5-32-544') | Select-Object -Unique
}

function New-VASRuntimeSecurity {
    $security = New-Object Security.AccessControl.FileSecurity
    $security.SetAccessRuleProtection($true, $false)
    foreach ($principal in @(Get-VASRuntimePrincipals)) {
        $sid = New-Object Security.Principal.SecurityIdentifier($principal)
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
        $security.AddAccessRule($rule)
    }
    return $security
}

function Test-VASRuntimeSecurity {
    param([Security.AccessControl.FileSecurity]$Security)
    $principals = @(Get-VASRuntimePrincipals)
    if (-not $Security.AreAccessRulesProtected) { return $false }
    if ($Security.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $principals) { return $false }
    $rules = @($Security.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne $principals.Count) { return $false }
    foreach ($rule in $rules) {
        if ($rule.IdentityReference.Value -notin $principals -or $rule.IsInherited -or
            $rule.AccessControlType -ne 'Allow' -or $rule.FileSystemRights -ne 'FullControl' -or
            $rule.InheritanceFlags -ne 'None' -or $rule.PropagationFlags -ne 'None') { return $false }
    }
    return @($rules | ForEach-Object { $_.IdentityReference.Value } | Select-Object -Unique).Count -eq $principals.Count
}

function Assert-VASRuntimePath {
    param([string]$Path, [string]$ExpectedType = 'File')
    try { Assert-VASLocalStatePath -Path $Path -ExpectedType $ExpectedType }
    catch { throw 'VAS_RUNTIME_STATE_UNSAFE: Use a local Windows state folder without links (-StateRoot), or restore the default state location.' }
}

function Protect-VASRuntimeFile {
    param([string]$Path)
    Assert-VASRuntimePath $Path
    if (-not [IO.File]::Exists($Path)) { return }
    try {
        $security = [IO.File]::GetAccessControl($Path)
        # Do not take ownership of an unexpected user's file or read its token.
        if ($security.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @(Get-VASRuntimePrincipals)) { throw 'owner' }
        if (-not (Test-VASRuntimeSecurity $security)) {
            [IO.File]::SetAccessControl($Path, (New-VASRuntimeSecurity))
        }
        if (-not (Test-VASRuntimeSecurity ([IO.File]::GetAccessControl($Path)))) { throw 'ACL verification' }
    } catch { throw 'VAS_RUNTIME_STATE_UNSAFE: Runtime file permissions could not be verified. Use your own local Windows state folder (-StateRoot). Existing files were preserved.' }
}

function New-VASRuntimeSecureStream {
    param([string]$Path)
    Assert-VASRuntimePath $Path
    $stream = $null
    try {
        $security = New-VASRuntimeSecurity
        $security.SetOwner([Security.Principal.WindowsIdentity]::GetCurrent().User)
        # This .NET Framework overload sets the DACL at CreateNew, before any token bytes.
        $stream = [IO.FileStream]::new($Path, [IO.FileMode]::CreateNew,
            [Security.AccessControl.FileSystemRights]::Write, [IO.FileShare]::None,
            4096, [IO.FileOptions]::WriteThrough, $security)
        if (-not (Test-VASRuntimeSecurity ([IO.File]::GetAccessControl($Path)))) { throw 'ACL verification' }
        return $stream
    } catch {
        if ($null -ne $stream) { $stream.Dispose() }
        throw 'VAS_RUNTIME_STATE_UNSAFE: A private runtime file could not be created. Use a local Windows state folder with file permission support (-StateRoot).'
    }
}

function Save-VASRuntimeState {
    param([string]$Path, $Runtime)
    $temporary = Join-Path (Split-Path -Parent $Path) ('.runtime-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $stream = $null
    try {
        Protect-VASRuntimeFile $Path
        $stream = New-VASRuntimeSecureStream $temporary
        $bytes = [Text.Encoding]::UTF8.GetBytes(($Runtime | ConvertTo-Json -Compress))
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
        $stream.Dispose(); $stream = $null
        Protect-VASRuntimeFile $Path
        Assert-VASRuntimePath $temporary
        # ReplaceFile preserves destination metadata, so its DACL must be secured first.
        if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
        Protect-VASRuntimeFile $Path
    } catch { throw 'VAS_RUNTIME_STATE_UNSAFE: Private runtime state could not be saved. Check the local state folder permissions; existing state was not intentionally removed.' }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        try {
            Assert-VASRuntimePath $temporary
            if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        } catch { }
    }
}

function Read-VASRuntimeStateText {
    param([string]$Path)
    Protect-VASRuntimeFile $Path
    if (-not [IO.File]::Exists($Path)) { return $null }
    try { return [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8) }
    catch { throw 'VAS_RUNTIME_STATE_UNSAFE: Runtime state could not be read safely. Existing state was preserved; check local file access before retrying.' }
}

function Remove-VASRuntimeStateFile {
    param([string]$Path)
    Protect-VASRuntimeFile $Path
    try { if ([IO.File]::Exists($Path)) { [IO.File]::Delete($Path) } }
    catch { throw 'VAS_RUNTIME_STATE_UNSAFE: Runtime state could not be removed safely. Check local file access before retrying.' }
}
