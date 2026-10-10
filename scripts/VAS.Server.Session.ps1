Import-Module (Join-Path $PSScriptRoot 'VAS.Session.psm1') -Force

function New-VASSessionToken {
    $bytes = New-Object byte[] 32
    $rng = New-Object Security.Cryptography.RNGCryptoServiceProvider
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_'))
}

function Read-VASSessionBody {
    param([Net.HttpListenerRequest]$Request)
    if ($Request.ContentLength64 -gt 65536) { throw 'session_input_too_large' }
    if ($Request.ContentType -notmatch '^application/json(?:\s*;|$)') { throw 'session_invalid' }
    $stream = New-Object IO.MemoryStream
    $buffer = New-Object byte[] 8192
    try {
        while (($count = $Request.InputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($stream.Length + $count -gt 65536) { throw 'session_input_too_large' }
            $stream.Write($buffer, 0, $count)
        }
        # Preserve raw JSON for Python's duplicate-key and strict-number validation.
        $encoding = New-Object Text.UTF8Encoding($false, $true)
        return $encoding.GetString($stream.ToArray())
    } finally { $stream.Dispose() }
}

function Invoke-VASSessionHttpRoute {
    param([string]$Path, [Net.HttpListenerContext]$Context, $State)
    $request = $Context.Request
    $method = $request.HttpMethod.ToUpperInvariant()
    try {
        if ($Path -eq '/api/chat/sessions' -and $method -eq 'GET') {
            $result = Invoke-VASSessionWeb $State.RootPath 'list'
        } elseif ($Path -eq '/api/chat/session' -and $method -eq 'GET') {
            $inputText = @{ sessionId = [string]$request.QueryString['sessionId'] } | ConvertTo-Json -Compress
            $result = Invoke-VASSessionWeb $State.RootPath 'get' $inputText
        } elseif ($Path -eq '/api/chat/session/design' -and $method -eq 'POST') {
            $result = Invoke-VASSessionWeb $State.RootPath 'design' (Read-VASSessionBody $request)
        } else {
            Write-VASError $Context 404 'API 경로를 찾을 수 없습니다.'; return
        }
        Write-VASResponse $Context 200 $result
    } catch {
        $mapped = Get-VASSessionError $_.Exception.Message
        Write-VASError $Context $mapped.status $mapped.message $mapped.code
    }
}
