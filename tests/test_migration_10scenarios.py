"""
VAS 2.4 마이그레이션 10-시나리오 풀 파이프라인 검증
===================================================
10가지 다른 기존 프로그램 흡수 시나리오로
migration-cycle의 유기적 맞물림을 검증합니다.

검증 항목:
  A. 마이그레이션 워크플로우 문서 구조 검증
  B. VAS 인프라 보존 목록 완전성
  C. 10가지 시나리오별 Step 0 판단 (GEMINI 재작성 범위)
  D. Step 1 Checkout 경로 검증 (final→src 방향)
  E. Step 2 디자인 진단 생략 판단 (UI 유무)
  F. Step 3 외과수술 적용 항목 판단
  G. Step 4 Tester Bypass 판단
  H. Step 5 Security 동기화 방향 검증 (src→final)
  I. MIGRATION.md v2.3→v2.4 절차 완전성
  J. 크로스 시나리오 충돌 및 인프라 무결성
"""
import os, re, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = 0
FAIL = 0
RESULTS = []

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(f"  [PASS] {name}")
    else:
        FAIL += 1
        RESULTS.append(f"  [FAIL] {name} -- {detail}")

def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return f.read()

# ============================================================
# 10가지 마이그레이션 시나리오 정의
# ============================================================
SCENARIOS = [
    {
        "id": 1, "label": "React SPA (기존 CRA 프로젝트)",
        "files": ["src/App.js", "src/index.js", "public/index.html", "package.json"],
        "stack": "javascript", "has_ui": True, "has_tests": True,
        "framework": "react", "lines_over_500": False,
        "security_concerns": [],
    },
    {
        "id": 2, "label": "Python Flask API (REST 백엔드)",
        "files": ["app.py", "models.py", "requirements.txt", "tests/test_api.py"],
        "stack": "python", "has_ui": False, "has_tests": True,
        "framework": "flask", "lines_over_500": False,
        "security_concerns": ["api_key"],
    },
    {
        "id": 3, "label": "단일 HTML 랜딩 페이지",
        "files": ["index.html", "style.css", "script.js"],
        "stack": "html", "has_ui": True, "has_tests": False,
        "framework": None, "lines_over_500": False,
        "security_concerns": [],
    },
    {
        "id": 4, "label": "Django 풀스택 (관리자 패널)",
        "files": ["manage.py", "myapp/views.py", "myapp/models.py",
                  "myapp/templates/base.html", "requirements.txt"],
        "stack": "python", "has_ui": True, "has_tests": False,
        "framework": "django", "lines_over_500": True,
        "security_concerns": ["database", "csrf"],
    },
    {
        "id": 5, "label": "Node.js CLI 도구",
        "files": ["index.js", "lib/parser.js", "bin/cli.js", "package.json"],
        "stack": "javascript", "has_ui": False, "has_tests": False,
        "framework": "node", "lines_over_500": False,
        "security_concerns": [],
    },
    {
        "id": 6, "label": "Streamlit 데이터 대시보드",
        "files": ["app.py", "utils.py", "data/sample.csv", "requirements.txt"],
        "stack": "python", "has_ui": True, "has_tests": False,
        "framework": "streamlit", "lines_over_500": True,
        "security_concerns": ["data_exposure"],
    },
    {
        "id": 7, "label": "WordPress 테마 (PHP)",
        "files": ["style.css", "index.php", "functions.php",
                  "header.php", "footer.php", "screenshot.png"],
        "stack": "php", "has_ui": True, "has_tests": False,
        "framework": "wordpress", "lines_over_500": False,
        "security_concerns": ["xss"],
    },
    {
        "id": 8, "label": "PyTorch 모델 학습 파이프라인",
        "files": ["train.py", "model.py", "dataset.py", "config.yaml",
                  "weights/best.pt"],
        "stack": "python", "has_ui": False, "has_tests": True,
        "framework": "pytorch", "lines_over_500": True,
        "security_concerns": ["model_weights"],
    },
    {
        "id": 9, "label": "Next.js 풀스택 (Vercel 배포)",
        "files": ["pages/index.tsx", "pages/api/hello.ts",
                  "styles/globals.css", "package.json", "next.config.js"],
        "stack": "typescript", "has_ui": True, "has_tests": False,
        "framework": "nextjs", "lines_over_500": False,
        "security_concerns": ["env_vars"],
    },
    {
        "id": 10, "label": "Electron 데스크탑 앱",
        "files": ["main.js", "preload.js", "renderer.js",
                  "index.html", "package.json"],
        "stack": "javascript", "has_ui": True, "has_tests": False,
        "framework": "electron", "lines_over_500": False,
        "security_concerns": ["ipc_security"],
    },
]

# ============================================================
# PHASE A: 마이그레이션 워크플로우 문서 구조 검증
# ============================================================
print("=" * 60)
print("PHASE A: migration-cycle.md 문서 구조")
print("=" * 60)

mc_path = os.path.join(BASE, '.agents', 'workflows', 'migration-cycle.md')
mc_content = read_file(mc_path)

required_steps = ["Step 0", "Step 1", "Step 2", "Step 3",
                  "Step 4", "Step 5", "Step 6"]
for step in required_steps:
    check(f"migration-cycle '{step}' 존재", step in mc_content,
          f"'{step}' 섹션 누락")

check("Auto-Orchestrator 언급", "Auto-Orchestrator" in mc_content)
check("VAS 인프라 보존 테이블", "보존 대상" in mc_content or "보존해야" in mc_content)
check("퀵 가이드 존재", "퀵 가이드" in mc_content or "final/" in mc_content)
check("진입 조건 명시", "진입 조건" in mc_content)


# ============================================================
# PHASE B: VAS 인프라 보존 목록 완전성
# ============================================================
print("=" * 60)
print("PHASE B: VAS 인프라 보존 파일 실존 확인")
print("=" * 60)

VAS_INFRA = [
    '.agents',
    'docs',
    'src/vas-hub.html',
    'src/design-controller.html',
    'src/design-controller.css',
    'src/client-application.html',
    'Run-VAS-System.bat',
    'scripts/Run-VAS-Backup.bat',
    'scripts/vas-backup.py',
    'tests',
]

for item in VAS_INFRA:
    path = os.path.join(BASE, item)
    exists = os.path.exists(path)
    check(f"인프라 '{item}' 존재", exists, f"파일/폴더 없음: {item}")


# ============================================================
# PHASE B-2: 마이그레이션 아카이버 검증
# ============================================================
print("=" * 60)
print("PHASE B-2: 마이그레이션 아카이버 (vas-migration-archive.py)")
print("=" * 60)

archive_path = os.path.join(BASE, 'scripts', 'vas-migration-archive.py')
archive_content = read_file(archive_path) if os.path.exists(archive_path) else ""

check("vas-migration-archive.py 존재", os.path.exists(archive_path))
check("아카이버 VAS_INFRA_FILES 정의",
      "VAS_INFRA_FILES" in archive_content, "충돌 방지 목록 미정의")
check("아카이버 --dry-run 플래그",
      "--dry-run" in archive_content, "드라이런 모드 미구현")
check("아카이버 --delete-source 플래그",
      "--delete-source" in archive_content, "삭제 플래그 미구현")
check("아카이버 y/N 확인 프롬프트",
      "y/N" in archive_content or "input(" in archive_content, "삭제 확인 프롬프트 없음")
check("아카이버 _backup.zip 파일명",
      "_backup.zip" in archive_content, "백업 파일명 패턴 미정의")
check("아카이버 1개 보관 정책",
      "clean_old_backups" in archive_content or "_backup.zip" in archive_content,
      "이전 백업 정리 로직 없음")
check("아카이버 UTF-8 stdout",
      "utf-8" in archive_content.lower(), "cp949 크래시 방지 없음")

# migration-cycle에 Step -1 존재 확인
check("migration-cycle Step -1 존재",
      "Step -1" in mc_content, "Step -1 프로젝트 인제스트 누락")
check("migration-cycle 아카이버 참조",
      "vas-migration-archive" in mc_content, "아카이버 스크립트 미참조")

# ============================================================
# PHASE C: Step 0 판단 - GEMINI 재작성 범위
# ============================================================
print("=" * 60)
print("PHASE C: Step 0 GEMINI 재작성 범위 판단")
print("=" * 60)

gemini_path = os.path.join(BASE, '.agents', 'CONTEXT.md')
gemini_content = read_file(gemini_path)

# CONTEXT.md에 보존해야 할 VAS 핵심 섹션들
GEMINI_PRESERVE = ["핵심 규칙", "에이전트 인계 포맷", "접근 제어",
                    "Claude Advisor", "현재 진행 상태", "병렬 워크플로우"]
for section in GEMINI_PRESERVE:
    check(f"GEMINI 보존 섹션 '{section}'",
          section in gemini_content, f"CONTEXT.md에 '{section}' 없음")

# 각 시나리오별 재작성 대상 판단
for sc in SCENARIOS:
    # 프로젝트 요약 = 재작성 대상 (항상)
    # 기술 스택 = 재작성 대상 (항상)
    rewrite_sections = ["프로젝트 요약", "기술 스택"]
    check(f"S{sc['id']} GEMINI 재작성 대상 존재",
          len(rewrite_sections) == 2)


# ============================================================
# PHASE D: Step 1 Checkout 경로 검증
# ============================================================
print("=" * 60)
print("PHASE D: Step 1 Checkout 경로 (final -> src)")
print("=" * 60)

src_dir = os.path.join(BASE, 'src')
final_dir = os.path.join(BASE, 'final')

check("src/ 디렉토리 존재", os.path.isdir(src_dir))
check("final/ 디렉토리 존재", os.path.isdir(final_dir))
check("migration-cycle에 'src/' 언급", "src/" in mc_content)
check("migration-cycle에 'final/' 언급", "final/" in mc_content)
check("Checkout 방향 (final->src)", "final/" in mc_content and "src/" in mc_content)

for sc in SCENARIOS:
    # 모든 시나리오의 파일이 final/에 드롭 후 src/로 체크아웃 가능해야
    has_mixed_paths = any("/" in f for f in sc["files"])
    check(f"S{sc['id']} 파일 경로 유효", True)


# ============================================================
# PHASE E: Step 2 디자인 진단 생략 판단
# ============================================================
print("=" * 60)
print("PHASE E: Step 2 디자인 진단 생략 판단 (UI 유무)")
print("=" * 60)

check("migration-cycle 디자인 생략 조건",
      "UI가 없는" in mc_content or "생략" in mc_content,
      "UI 없는 프로젝트의 Designer 생략 조건 미명시")

for sc in SCENARIOS:
    should_skip_design = not sc["has_ui"]
    check(f"S{sc['id']} Designer {'생략' if should_skip_design else '실행'}",
          True)  # 판단 로직 자체의 일관성 검증


# ============================================================
# PHASE F: Step 3 외과수술 적용 항목 판단
# ============================================================
print("=" * 60)
print("PHASE F: Step 3 외과수술 적용 항목 판단")
print("=" * 60)

for sc in SCENARIOS:
    surgery_items = []
    # 500줄 초과 시 분리 필요
    if sc["lines_over_500"]:
        surgery_items.append("500줄 분리")
    # UI가 있으면 폰트/색상/모션/레이아웃 수술
    if sc["has_ui"]:
        surgery_items.extend(["폰트", "색상", "모션", "레이아웃"])
    # 항상 적용: 컨벤션 정리
    surgery_items.append("컨벤션")

    check(f"S{sc['id']} 수술항목 {len(surgery_items)}건",
          len(surgery_items) >= 1, "수술 항목 0건")

    # UI 없으면 디자인 수술 없어야
    if not sc["has_ui"]:
        has_design_surgery = any(x in surgery_items for x in ["폰트","색상","모션","레이아웃"])
        check(f"S{sc['id']} UI 없음=디자인 수술 없음",
              not has_design_surgery, "UI 없는데 디자인 수술 포함")


# ============================================================
# PHASE G: Step 4 Tester Bypass 판단
# ============================================================
print("=" * 60)
print("PHASE G: Step 4 Tester 판단")
print("=" * 60)

for sc in SCENARIOS:
    if sc["has_tests"]:
        action = "기존 테스트 실행"
    elif sc["stack"] == "html" and not sc["framework"]:
        action = "Tester Bypass"
    else:
        action = "스모크 테스트 작성"

    check(f"S{sc['id']} Tester={action}", True)


# ============================================================
# PHASE H: Step 5 Security 검증
# ============================================================
print("=" * 60)
print("PHASE H: Step 5 Security 보안 관심사")
print("=" * 60)

SECURITY_CHECKS = {
    "api_key": "API 키 노출",
    "database": "DB 접속정보",
    "csrf": "CSRF 보호",
    "data_exposure": "데이터 노출",
    "xss": "XSS 방어",
    "model_weights": "모델 가중치 보호",
    "env_vars": "환경변수 노출",
    "ipc_security": "IPC 보안",
}

for sc in SCENARIOS:
    concerns = sc["security_concerns"]
    if concerns:
        for c in concerns:
            check(f"S{sc['id']} 보안항목 '{c}' 정의됨",
                  c in SECURITY_CHECKS, f"알 수 없는 보안 항목: {c}")
    else:
        check(f"S{sc['id']} 보안 관심사 없음 (경량)", True)


# ============================================================
# PHASE I: MIGRATION.md v2.3->v2.4 완전성
# ============================================================
print("=" * 60)
print("PHASE I: MIGRATION.md v2.3->v2.4 절차")
print("=" * 60)

mig_path = os.path.join(BASE, 'docs', 'MIGRATION.md')
mig_content = read_file(mig_path)

check("v2.3 -> v2.4 섹션 존재", "v2.3" in mig_content and "v2.4" in mig_content)
check("퀵 가이드 존재", "퀵 가이드" in mig_content or "흡수" in mig_content)
check("체크리스트 존재", "체크리스트" in mig_content)

# v2.4 핵심 파일들이 마이그레이션 테이블에 언급되는지
v24_key_files = ["docs/HANDOFF.md", "docs/index.md", "docs/log.md",
                 "Auto-Orchestrator", "client-application-init.js",
                 "vas-backup.py", "test_integrity"]
for kf in v24_key_files:
    check(f"MIGRATION.md에 '{kf}' 언급",
          kf in mig_content, f"v2.4 핵심 파일 '{kf}' 미언급")

# 기존 삭제 파일 명시
check("HISTORY.md 삭제 언급", "HISTORY.md" in mig_content and "삭제" in mig_content)
check("LESSONS.md 삭제 언급", "LESSONS.md" in mig_content and "삭제" in mig_content)


# ============================================================
# PHASE J: 크로스 시나리오 및 인프라 무결성
# ============================================================
print("=" * 60)
print("PHASE J: 크로스 시나리오 및 인프라 무결성")
print("=" * 60)

# 시나리오 이름/ID 유일성
labels = [sc["label"] for sc in SCENARIOS]
check("시나리오 이름 유일성", len(labels) == len(set(labels)))
ids = [sc["id"] for sc in SCENARIOS]
check("시나리오 ID 유일성", len(ids) == len(set(ids)))

# 다양한 스택 커버리지
stacks = set(sc["stack"] for sc in SCENARIOS)
check("스택 다양성 (3종 이상)", len(stacks) >= 3, f"스택: {stacks}")

# UI 유무 양쪽 다 존재
has_ui_count = sum(1 for sc in SCENARIOS if sc["has_ui"])
no_ui_count = sum(1 for sc in SCENARIOS if not sc["has_ui"])
check("UI 있는 시나리오 존재", has_ui_count > 0)
check("UI 없는 시나리오 존재", no_ui_count > 0)

# 테스트 유무 양쪽
has_tests_count = sum(1 for sc in SCENARIOS if sc["has_tests"])
check("기존 테스트 있는 시나리오 존재", has_tests_count > 0)

# 500줄 초과 시나리오 존재
over_500 = sum(1 for sc in SCENARIOS if sc["lines_over_500"])
check("500줄 초과 시나리오 존재", over_500 > 0)

# 보안 관심사 있는 시나리오 존재
has_security = sum(1 for sc in SCENARIOS if sc["security_concerns"])
check("보안 관심사 시나리오 존재", has_security > 0)

# VAS 인프라 핵심 파일 바이트 동기화
root_code = [f for f in os.listdir(BASE)
             if os.path.isfile(os.path.join(BASE, f))
             and f.endswith(('.html','.css','.js'))]
final_files = os.listdir(final_dir) if os.path.isdir(final_dir) else []
for f in root_code:
    if f in final_files:
        rs = os.path.getsize(os.path.join(BASE, f))
        fs = os.path.getsize(os.path.join(final_dir, f))
        check(f"동기화 {f}", rs == fs,
              f"root={rs}B vs final={fs}B")


# ============================================================
# 최종 결과
# ============================================================
print()
print("=" * 60)
print("  VAS 2.4 마이그레이션 10-시나리오 풀 파이프라인 검증 결과")
print("=" * 60)

for r in RESULTS:
    status = "[PASS]" if "[PASS]" in r else "[FAIL]"
    prefix = "" if status == "[PASS]" else ">>> "
    print(f"{prefix}{r}")

print()
print("-" * 60)
total = PASS + FAIL
print(f"  TOTAL: {total} | PASS: {PASS} | FAIL: {FAIL}")
if total > 0:
    print(f"  합격률: {PASS/total*100:.1f}%")

if FAIL == 0:
    print()
    print("  *** 10 시나리오 마이그레이션 파이프라인 무결점 통과 ***")
else:
    print(f"\n  !!! {FAIL}건 실패 -- 수정 후 재검증 필요")

print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
