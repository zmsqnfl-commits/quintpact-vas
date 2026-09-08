# pre-commit 훅 (Windows 버전) — 커밋 전 자동 검증
# check-staged.py와 함께 같은 폴더에 두고 PowerShell 래퍼로 실행하세요.
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
try {
    $python = Get-Command python -ErrorAction Stop
    & $python.Source (Join-Path $PSScriptRoot 'check-staged.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch { Write-Host '[BLOCKED] Could not inspect staged content.'; exit 2 }

Write-Host "[Pre-Commit] 검증 통과 ✓"
exit 0
