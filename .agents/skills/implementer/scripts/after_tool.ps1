# AfterTool Hook — 도구 실행 후 로깅 및 검증 (Windows 버전)
# /setup-from-application 실행 시 프로젝트에 맞게 커스터마이징됩니다.

Write-Host "[AfterTool] 실행 완료: $env:TOOL_NAME on $env:TARGET_PATH (결과: $env:EXIT_CODE)"

# TODO: 프로젝트별 로깅/검증 로직 추가
# 예시: 500줄 제한 자동 체크
# if ($env:TOOL_NAME -eq "write_to_file") {
#     $lineCount = (Get-Content $env:TARGET_PATH | Measure-Object -Line).Lines
#     if ($lineCount -gt 500) {
#         Write-Host "[WARNING] $env:TARGET_PATH 가 ${lineCount}줄로 500줄 제한을 초과합니다."
#     }
# }

exit 0
