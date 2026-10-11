$script:SensitiveKeyPattern = '(?i)((?:[a-z0-9]+[_-])*(?:password|pgpassword|passwd|pwd|passphrase|secret|secrets|credential|credentials|api[_ -]?key|(?:access|refresh|auth|session)[_ -]?token|token|client[_ -]?secret|authorization|private[_ -]?key|database[_ -]?url|db[_ -]?(?:url|password|pass)|(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|aws[_ -]?(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|connection[_ -]?string|github[_ -]?pat)|file(name|path|content)?|(^|_)path$|folder|directory|contact|phone|e.?mail)'
$script:SensitiveValuePattern = '(?i)(?:\b(?:[a-z0-9]+[_-])*(?:password|pgpassword|passwd|pwd|passphrase|secret|secrets|credential|credentials|api[_ -]?key|(?:access|refresh|auth|session)[_ -]?token|token|client[_ -]?secret|authorization|private[_ -]?key|database[_ -]?url|db[_ -]?(?:url|password|pass)|(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|aws[_ -]?(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|connection[_ -]?string|github[_ -]?pat)\b["'']?\s*(?:(?:/\*[\s\S]*?\*/|//[^\r\n]*)\s*)*(?:\]\s*(?:(?:/\*[\s\S]*?\*/|//[^\r\n]*)\s*)*)?[:=]|(?:\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[a-z0-9_-]{12,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}|\b(?:Bearer|Basic)\s+[a-z0-9._~+/=-]{10,}|\beyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}|-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----|\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|rediss?|mssql)(?:\+[a-z0-9_.-]+)?://\S+|\b[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b(?:\+?82[- ]?0?1[016789]|01[016789])[- ]?\d{3,4}[- ]?\d{4}))'
$script:PathValuePattern = '(?i)(?:^|[\s''"(])(?:[a-z]:[\\/]|\\\\|file:/+|/(?:home|users?|var|tmp|etc|mnt|volumes)/|\.{1,2}[\\/])'
$script:FileValuePattern = '(?i)(?:^|[\s''"(])[^<>:"/\\|?*\r\n]{1,100}\.[a-z0-9]{1,8}(?:$|[\s''",)])'

function Get-VASCredentialView {
    param($Value)
    $text = [string]$Value
    $entities = @{ amp = '&'; colon = ':'; equals = '='; quot = '"'; apos = "'"; lt = '<'; gt = '>'; sol = '/'; bsol = '\'; percnt = '%'; lowbar = '_'; hyphen = '-' }
    $encoded = '\\\\(?=u[a-f0-9]{4}|x[a-f0-9]{2})|\\(?:u([a-f0-9]{4})|x([a-f0-9]{2}))|%([a-f0-9]{2})|&#(x[a-f0-9]{1,6}|[0-9]{1,7});|&(amp|colon|equals|quot|apos|lt|gt|sol|bsol|percnt|lowbar|hyphen);'
    for ($pass = 0; $pass -lt 2; $pass++) {
        try { $text = $text.Normalize([Text.NormalizationForm]::FormKC) } catch { }
        $text = [regex]::Replace($text, $encoded, {
            param($m)
            if ($m.Value -eq '\\') { return '\' }
            if ($m.Groups[5].Success) { return $entities[$m.Groups[5].Value.ToLowerInvariant()] }
            $part = ($m.Groups[1..4] | Where-Object Success | Select-Object -First 1).Value
            $radix = if ($m.Groups[4].Success -and $part -notmatch '^x') { 10 } else { 16 }
            $number = [Convert]::ToInt32(($part -replace '^x', ''), $radix)
            if ($number -gt 0x10ffff -or ($number -ge 0xd800 -and $number -le 0xdfff) -or ($m.Groups[3].Success -and $number -gt 127)) { return $m.Value }
            return [char]::ConvertFromUtf32($number)
        }, [Text.RegularExpressions.RegexOptions]::IgnoreCase)
    }
    try { $text = $text.Normalize([Text.NormalizationForm]::FormKC) } catch { }
    $text = [regex]::Replace($text, '[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]', '')
    $gap = '\s*(?:(?:/\*[\s\S]*?\*/|//[^\r\n]*)\s*)*'
    $literal = '(?<![a-z0-9_"''`])(?:br|rb|r|u|b)?(?:"(?:\\.|[^"\\])*"|''(?:\\.|[^''\\])*''|`(?:\\.|[^`\\])*`)(?!["''`])'
    return [regex]::Replace($text, ($literal + '(?:' + $gap + '(?:[+\\]' + $gap + ')?' + $literal + ')+'), {
        param($m)
        $tokens = [regex]::Matches($m.Value, '/\*[\s\S]*?\*/|//[^\r\n]*|"(?:\\.|[^"\\])*"|''(?:\\.|[^''\\])*''|`(?:\\.|[^`\\])*`')
        $parts = @($tokens | Where-Object { $_.Value -match '^["''`]' } | ForEach-Object { $_.Value.Substring(1, $_.Value.Length - 2) })
        return '"' + ($parts -join '') + '"'
    }, [Text.RegularExpressions.RegexOptions]::IgnoreCase)
}

function Test-VASPrivateText {
    param($Value)
    $decoded = Get-VASCredentialView $Value
    for ($i = 0; $i -lt 4; $i++) {
        $next = [regex]::Replace($decoded, '"(?:\\.|[^"\\])*"', { param($match) try { $items = @(ConvertFrom-Json ('[' + $match.Value + ']') -ErrorAction Stop); ' ' + [string]$items[0] + ' ' } catch { $match.Value } })
        if ($next -eq $decoded) { break }
        if ($i -eq 3) { return $true }
        $decoded = $next
    }
    if ($decoded -match $script:PathValuePattern -or $decoded.Trim() -match $script:FileValuePattern) { return $true }
    if ($decoded -match '(?i)\b[a-z][a-z0-9+.-]*://[^\s/\\"<>`?#]+@') { return $true }
    $xmlLabels = [regex]::Replace($decoded, '<(?:[^\s<>/=:]+:)?([a-z0-9_-]+)(?=[\s/>])', ' $1=', [Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $indexedLabels = [regex]::Replace($decoded, '["''`]?\s*(?:(?:/\*[\s\S]*?\*/|//[^\r\n]*)\s*)*\]', '=')
    if ($indexedLabels -match $script:SensitiveValuePattern -or $xmlLabels -match $script:SensitiveValuePattern) { return $true }
    return $false
}

function ConvertTo-VASSafeValue {
    param($Value, [int]$Depth = 0)

    if ($Depth -gt 8) { return '[depth-limit]' }
    if ($null -eq $Value) { return $null }
    if ($Value -is [string]) {
        $text = $Value
        if (Test-VASPrivateText $text) { return '[redacted]' }
        return $text.Substring(0, [Math]::Min(4000, $text.Length))
    }
    if ($Value -is [bool] -or $Value -is [ValueType]) { return $Value }
    if ($Value -is [Collections.IDictionary]) {
        $safe = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $name = [string]$key
            if ((Get-VASCredentialView $name) -notmatch $script:SensitiveKeyPattern -and -not (Test-VASPrivateText $name)) {
                $safe[$name] = ConvertTo-VASSafeValue $Value[$key] ($Depth + 1)
            }
        }
        return $safe
    }
    if ($Value -is [Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = @()
        foreach ($item in $Value) { $items += ,(ConvertTo-VASSafeValue $item ($Depth + 1)) }
        return ,$items
    }

    $safeObject = [ordered]@{}
    foreach ($property in $Value.PSObject.Properties) {
        if ((Get-VASCredentialView $property.Name) -notmatch $script:SensitiveKeyPattern -and -not (Test-VASPrivateText $property.Name)) {
            $safeObject[$property.Name] = ConvertTo-VASSafeValue $property.Value ($Depth + 1)
        }
    }
    return $safeObject
}

function ConvertTo-VASSafeMemoryIdentifier {
    param($Value, [string]$Fallback = '')
    $text = [string]$Value
    if ($text -match '^[a-zA-Z0-9._-]{1,80}$' -and $text -notmatch $script:SensitiveValuePattern) { return $text }
    return $Fallback
}

function ConvertTo-VASMemoryId {
    param($Value)
    $text = [string]$Value
    if ($text -match '^[a-f0-9]{32}$') { return $text.ToLowerInvariant() }
    if ($text -match '^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$') { return $text.Replace('-', '').ToLowerInvariant() }
    if ($text -notmatch '^[a-z0-9_-]{1,64}$' -or (Test-VASPrivateText $text)) { return [Guid]::NewGuid().ToString('N') }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes('vas-memory-id:' + $text)))).Replace('-', '').Substring(0, 32).ToLowerInvariant() }
    finally { $sha.Dispose() }
}
