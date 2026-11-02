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
        try { return $encoding.GetString($stream.ToArray()) }
        catch [Text.DecoderFallbackException] { throw 'session_invalid' }
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

function Invoke-VASProjectPromptHttpRoute {
    param([Net.HttpListenerContext]$Context, $State)
    if ($State.Layout -ne 'project') {
        Write-VASError $Context 404 '프로젝트 폴더에서 실행한 VAS에서만 사용할 수 있습니다.' 'project_prompt_layout'; return
    }
    $request = $Context.Request
    try {
        if ($request.Url.Query.Length -gt 0) { throw 'project_prompt_invalid' }
        switch ($request.HttpMethod.ToUpperInvariant()) {
            'GET' {
                if ($request.HasEntityBody) { throw 'project_prompt_invalid' }
                $result = Invoke-VASProjectPromptProcess $State.RootPath 'get'
            }
            'PUT' { $result = Invoke-VASProjectPromptProcess $State.RootPath 'save' (Read-VASSessionBody $request) }
            default {
                $Context.Response.Headers['Allow'] = 'GET, PUT'
                Write-VASError $Context 405 '지원하지 않는 요청입니다.' 'project_prompt_method'; return
            }
        }
        Write-VASResponse $Context 200 $result
    } catch {
        $code = $_.Exception.Message
        switch ($code) {
            'project_prompt_conflict' { $status = 409; $message = '다른 곳에서 지시를 변경했습니다. 최신 저장본과 비교하세요.' }
            'project_prompt_corrupt' { $status = 409; $message = '기존 지시 파일의 형식을 읽을 수 없습니다. 원본을 확인하세요.' }
            'project_prompt_sensitive' { $status = 400; $message = '비밀값·개인 경로·연락처를 지우고 다시 저장하세요.' }
            'python_unavailable' { $status = 503; $message = '프로젝트 지시를 열려면 Python 3.10 이상이 필요합니다.' }
            'project_prompt_unsafe' { $status = 409; $message = '지시 파일이 안전한 일반 파일인지 확인하세요.' }
            'project_prompt_layout' { $status = 409; $message = '현재 폴더가 정상적인 VAS 프로젝트인지 확인하세요.' }
            { $_ -in @('session_input_too_large','project_prompt_too_large') } {
                $status = 413; $code = 'project_prompt_too_large'; $message = '프로젝트 지시가 너무 깁니다.'
            }
            { $_ -in @('session_invalid','project_prompt_invalid') } {
                $status = 400; $code = 'project_prompt_invalid'; $message = '작업 지시의 형식과 길이를 확인하세요.'
            }
            'project_prompt_busy' { $status = 503; $message = '다른 작업이 저장 중입니다. 잠시 후 다시 시도하세요.' }
            default { $status = 503; $code = 'project_prompt_unavailable'; $message = '프로젝트 지시를 읽거나 저장할 수 없습니다.' }
        }
        Write-VASError $Context $status $message $code
    }
}

function Invoke-VASProjectProgressRoute {
    param([Net.HttpListenerContext]$Context, $State)
    if ($State.Layout -ne 'project') {
        Write-VASError $Context 404 '현재 프로젝트에서만 진행 요약을 조회할 수 있습니다.' 'shared_progress_layout'; return
    }
    $request = $Context.Request
    if ($request.HttpMethod -ne 'GET') {
        $Context.Response.Headers['Allow'] = 'GET'
        Write-VASError $Context 405 '지원하지 않는 요청입니다.' 'shared_progress_method'; return
    }
    if ($request.Url.Query.Length -gt 0 -or $request.HasEntityBody) {
        Write-VASError $Context 400 '요청에 경로나 본문을 포함하지 마세요.' 'shared_progress_invalid_request'; return
    }
    try {
        $result = Invoke-VASProjectPromptProcess $State.RootPath 'progress'
        Write-VASResponse $Context 200 $result
    } catch {
        $code = $_.Exception.Message
        if ($code -in @('shared_progress_invalid', 'shared_progress_unsafe', 'shared_progress_full')) {
            Write-VASError $Context 409 '공유 진행 기록을 확인할 수 없습니다.' $code
        } else {
            Write-VASError $Context 503 '프로젝트 진행 기록에 접근할 수 없습니다.' 'shared_progress_unavailable'
        }
    }
}
