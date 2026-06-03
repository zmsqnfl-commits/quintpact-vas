# BeforeTool Hook — 도구 실행 전 RBAC/ABAC 권한 체크 (Windows 버전)
# 이 파일은 스킬 2.0 라이프사이클 훅의 템플릿입니다.
# /setup-from-application 실행 시 프로젝트에 맞게 커스터마이징됩니다.

# 사용법: 하네스가 도구 실행 전 자동으로 이 스크립트를 호출합니다.
# 종료 코드 0 = 허용, 1 = 차단

Write-Host "[BeforeTool] 권한 체크 시작: $env:TOOL_NAME on $env:TARGET_PATH"

# TODO: 프로젝트별 RBAC/ABAC 권한 검증 로직 추가
# 예시:
# if ($env:AGENT_ROLE -eq "reviewer" -and $env:TOOL_NAME -eq "write_to_file") {
#     Write-Host "[DENIED] Reviewer는 파일 쓰기 권한이 없습니다."
#     exit 1
# }

# denied_write_paths 검증 예시:
# $deniedPaths = @("final\*", "tests\*", ".agents\*")
# foreach ($pattern in $deniedPaths) {
#     if ($env:TARGET_PATH -like $pattern) {
#         Write-Host "[DENIED] $env:TARGET_PATH 는 쓰기 금지 경로입니다."
#         exit 1
#     }
# }

exit 0
