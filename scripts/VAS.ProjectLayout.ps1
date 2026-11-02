# Current starters own their root. Version 1 starters keep the engine in .vas.
function Get-VASRuntimeLayout {
    param([Parameter(Mandatory)][string]$Root, [switch]$ForServer)
    $path = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $installedEngine = Split-Path -Parent $PSScriptRoot
    if ($ForServer -and
        -not $path.Equals($installedEngine, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'VAS_PROJECT_ENGINE_ROOT_REQUIRED'
    }
    $nested = [IO.Path]::GetFileName($path) -eq '.vas'
    if (-not $nested -and -not (Test-Path -LiteralPath (Join-Path $path 'project-layout.json')) -and
        -not (Test-Path -LiteralPath (Join-Path $path 'ui'))) {
        if (Test-Path -LiteralPath (Join-Path $path '.vas\project-layout.json')) { throw 'VAS_PROJECT_ENGINE_ROOT_REQUIRED' }
        if ($ForServer) {
            # Only an identified pre-2.12 developer tool may publish its historical src/.
            $package = Get-Content -Raw -LiteralPath (Join-Path $path 'package.json') -Encoding UTF8 | ConvertFrom-Json
            if ($package.name -cne 'quintpact-vas' -or $package.version -notmatch '^2\.(?:[0-9]|1[01])\.\d+$' -or
                -not (Test-Path -LiteralPath (Join-Path $path 'src\vas-hub.html') -PathType Leaf)) { throw 'VAS_PROJECT_LAYOUT_INVALID' }
        }
        return 'tool'
    }
    try {
        $dir = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        while ($null -ne $dir) {
            if ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'linked layout' }
            $dir = $dir.Parent
        }
        $public = if ($nested) { 'src' } else { 'ui' }
        $dir = Get-Item -LiteralPath (Join-Path $path $public) -Force -ErrorAction Stop
        if (-not $dir.PSIsContainer -or ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'invalid UI' }
        foreach ($name in @('Run-VAS-System.bat', "$public\vas-hub.html", 'project-layout.json')) {
            $file = Get-Item -LiteralPath (Join-Path $path $name) -Force -ErrorAction Stop
            if ($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $file.LinkType) {
                throw 'invalid engine file'
            }
        }
        if ($file.Length -lt 1 -or $file.Length -gt 256) { throw 'invalid marker size' }
        $bytes = [IO.File]::ReadAllBytes($file.FullName)
        if ($bytes.Length -gt 256) { throw 'invalid marker size' }
        $text = [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
        # This is a fixed, app-independent marker. Reject repeated fields before PowerShell's parser collapses them.
        if ($text[0] -eq [char]0xfeff -or ([regex]::Matches($text, ':')).Count -ne 2) { throw 'invalid marker format' }
        $layout = $text | ConvertFrom-Json -ErrorAction Stop
        $keys = @($layout.PSObject.Properties | ForEach-Object { $_.Name })
        $expectedVersion = if ($nested) { 1 } else { 2 }
        if ($keys.Count -ne 2 -or 'layout' -cnotin $keys -or 'version' -cnotin $keys -or
            $layout.layout -cne 'vas-project' -or ($layout.version -isnot [int] -and $layout.version -isnot [long]) -or
            $layout.version -ne $expectedVersion) { throw 'invalid layout version' }
        return 'project'
    } catch { throw 'VAS_PROJECT_LAYOUT_INVALID' }
}
function Assert-VASLegacyWorkspace {
    param([Parameter(Mandatory)][string]$Root)
    if ((Get-VASRuntimeLayout $Root) -eq 'project') { throw 'VAS_PROJECT_ROOT_LAYOUT' }
}
function Assert-VASProjectStateLocation {
    param([string]$Engine, [string]$StatePath)
    $app = [IO.Path]::GetFullPath($Engine).TrimEnd('\')
    if ([IO.Path]::GetFileName($app) -eq '.vas') { $app = Split-Path -Parent $app }
    $state = [IO.Path]::GetFullPath($StatePath).TrimEnd('\')
    if ($state.Equals($app, [StringComparison]::OrdinalIgnoreCase) -or
        $state.StartsWith($app + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'VAS_PROJECT_PRIVATE_STATE_INSIDE_APP'
    }
}
