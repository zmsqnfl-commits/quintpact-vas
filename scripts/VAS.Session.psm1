Set-StrictMode -Version 2.0

function ConvertTo-VASSessionArgument {
    param([string]$Value)
    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

function Invoke-VASSessionProcess {
    param([string]$File, [string[]]$Arguments, [string]$InputText = '', [int]$Timeout = 15000)
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $File
    $start.Arguments = (($Arguments | ForEach-Object { ConvertTo-VASSessionArgument $_ }) -join ' ')
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $encoding = New-Object Text.UTF8Encoding($false)
    $start.StandardOutputEncoding = $encoding
    $start.StandardErrorEncoding = $encoding
    $start.EnvironmentVariables['PYTHONUTF8'] = '1'
    $start.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'session_bridge_unavailable' }
        $output = $process.StandardOutput.ReadToEndAsync()
        $errors = $process.StandardError.ReadToEndAsync()
        if ($InputText) {
            $inputBytes = $encoding.GetBytes($InputText)
            $process.StandardInput.BaseStream.Write($inputBytes, 0, $inputBytes.Length)
            $process.StandardInput.BaseStream.Flush()
        }
        $process.StandardInput.Close()
        if (-not $process.WaitForExit($Timeout)) {
            $process.Kill()
            throw 'session_bridge_timeout'
        }
        return [pscustomobject]@{ Output = $output.Result; Error = $errors.Result; ExitCode = $process.ExitCode }
    } finally {
        $process.Dispose()
    }
}

function Find-VASSessionPython {
    $candidates = @()
    if ($env:VAS_PYTHON) { $candidates += @{ file = $env:VAS_PYTHON; prefix = @() } }
    $candidates += @{ file = 'python.exe'; prefix = @() }
    $candidates += @{ file = 'py.exe'; prefix = @('-3') }
    foreach ($candidate in $candidates) {
        try {
            $command = Get-Command -Name $candidate.file -CommandType Application -ErrorAction Stop | Select-Object -First 1
            $check = Invoke-VASSessionProcess $command.Source (@($candidate.prefix) + @('--version')) '' 2500
            if ($check.ExitCode -eq 0 -and ($check.Output + ' ' + $check.Error) -match 'Python\s+(\d+)\.(\d+)') {
                if ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 10) {
                    return @{ file = $command.Source; prefix = @($candidate.prefix) }
                }
            }
        } catch { }
    }
    throw 'python_unavailable'
}

function Invoke-VASSessionWeb {
    param([string]$Root, [ValidateSet('list', 'get', 'design')][string]$Operation, [string]$InputText = '{}')
    $script = Join-Path $PSScriptRoot 'vas-session.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'session_bridge_unavailable' }
    $python = Find-VASSessionPython
    $arguments = @($python.prefix) + @('-B', $script, '--vas-root', $Root, 'web', $Operation)
    $execution = Invoke-VASSessionProcess $python.file $arguments $InputText
    try { $result = $execution.Output | ConvertFrom-Json } catch { throw 'session_bridge_invalid' }
    if ($execution.ExitCode -ne 0) {
        $code = [string]$result.code
        if ($code -notmatch '^(session_[a-z_]+|revision_[a-z_]+|target_unavailable)$') { $code = 'session_invalid' }
        throw $code
    }
    return $result
}

function Get-VASSessionError {
    param([string]$Code)
    $status = 400
    $message = '저장된 작업 설정과 입력값을 확인하세요.'
    if ($Code -eq 'revision_conflict') { $status = 409; $message = '채팅이나 다른 화면에서 설정이 변경됐습니다. 최신 설정을 읽은 뒤 다시 적용하세요.' }
    elseif ($Code -eq 'target_unavailable') { $status = 409; $message = '연결된 작업 폴더를 확인할 수 없습니다. 채팅에서 작업 폴더를 확인하세요.' }
    elseif ($Code -eq 'session_not_found') { $status = 404; $message = '저장된 작업이 없습니다. 채팅에서 연결할 작업을 확인하세요.' }
    elseif ($Code -eq 'session_input_too_large') { $status = 413; $message = '디자인 설정이 너무 큽니다.' }
    elseif ($Code -eq 'python_unavailable') { $status = 503; $message = '설정 연동에는 Python 3.10 이상이 필요합니다.' }
    elseif ($Code -match '^session_(store_|bridge_)') { $status = 503; $message = '로컬 작업 설정을 읽거나 저장하지 못했습니다. 채팅에서 설정 상태를 확인하세요.' }
    if ($Code -notmatch '^(session_[a-z_]+|revision_[a-z_]+|target_unavailable|python_unavailable)$') { $Code = 'session_invalid' }
    return @{ status = $status; code = $Code; message = $message }
}

Export-ModuleMember -Function Invoke-VASSessionWeb, Get-VASSessionError
