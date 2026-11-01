# The starter owns its parent as an app. The HTTP server only serves its engine.
function Get-VASRuntimeLayout {
    param([Parameter(Mandatory)][string]$Root)
    $path = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $installedEngine = Split-Path -Parent $PSScriptRoot
    if ((Split-Path -Leaf $installedEngine) -eq '.vas' -and
        -not $path.Equals($installedEngine, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'VAS_PROJECT_ENGINE_ROOT_REQUIRED'
    }
    if ([IO.Path]::GetFileName($path) -ne '.vas') {
        if ((Test-Path -LiteralPath (Join-Path $path '.vas\project-layout.json')) -or
            (Test-Path -LiteralPath (Join-Path $path 'project-layout.json'))) {
            throw 'VAS_PROJECT_ENGINE_ROOT_REQUIRED'
        }
        return 'tool'
    }
    try {
        $dir = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        while ($null -ne $dir) {
            if ($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'linked layout' }
            $dir = $dir.Parent
        }
        $src = Get-Item -LiteralPath (Join-Path $path 'src') -Force -ErrorAction Stop
        if (-not $src.PSIsContainer -or ($src.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'invalid src' }
        foreach ($name in @('Run-VAS-System.bat', 'src\vas-hub.html', 'project-layout.json')) {
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
        if ($keys.Count -ne 2 -or 'layout' -cnotin $keys -or 'version' -cnotin $keys -or
            $layout.layout -cne 'vas-project' -or ($layout.version -isnot [int] -and $layout.version -isnot [long]) -or
            $layout.version -ne 1) { throw 'invalid layout version' }
        return 'project'
    } catch { throw 'VAS_PROJECT_LAYOUT_INVALID' }
}
function Assert-VASLegacyWorkspace {
    param([Parameter(Mandatory)][string]$Root)
    if ((Get-VASRuntimeLayout $Root) -eq 'project') { throw 'VAS_PROJECT_ROOT_LAYOUT' }
}
function Assert-VASProjectStateLocation {
    param([string]$Engine, [string]$StatePath)
    $app = [IO.Path]::GetFullPath((Split-Path -Parent $Engine)).TrimEnd('\')
    $state = [IO.Path]::GetFullPath($StatePath).TrimEnd('\')
    if ($state.Equals($app, [StringComparison]::OrdinalIgnoreCase) -or
        $state.StartsWith($app + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'VAS_PROJECT_PRIVATE_STATE_INSIDE_APP'
    }
}
