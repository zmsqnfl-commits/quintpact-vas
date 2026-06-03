# pre-commit 훅 (Windows 버전) — 커밋 전 자동 검증
# 이 파일을 .git/hooks/pre-commit 으로 복사하세요.
# /setup-from-application 실행 시 프로젝트에 맞게 커스터마이징됩니다.

Write-Host "[Pre-Commit] 커밋 전 검증 시작..."

# 1. 500줄 제한 체크
$overLimit = @()
Get-ChildItem -Path "src" -Recurse -Include "*.py","*.js","*.ts" | ForEach-Object {
    $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
    if ($lines -gt 500) {
        $overLimit += "$($_.FullName): ${lines}줄"
    }
}

if ($overLimit.Count -gt 0) {
    Write-Host "[BLOCKED] 500줄 초과 파일 발견:"
    $overLimit | ForEach-Object { Write-Host "  $_" }
    exit 1
}

# 2. 민감 데이터 패턴 체크 (ABAC sensitive_data_guard)
$staged = git diff --cached --name-only
$sensitive = @()
foreach ($file in $staged) {
    if (Test-Path $file) {
        $content = Get-Content $file -Raw
        if ($content -match "(password|secret|api_key|private_key)\s*=") {
            $sensitive += $file
        }
    }
}

if ($sensitive.Count -gt 0) {
    Write-Host "[WARNING] 민감 데이터 패턴 발견:"
    $sensitive | ForEach-Object { Write-Host "  $_" }
    if ($env:SKIP_SENSITIVE -ne "1") {
        Write-Host "계속하려면: `$env:SKIP_SENSITIVE='1'; git commit"
        exit 1
    }
}

Write-Host "[Pre-Commit] 검증 통과 ✓"
exit 0
