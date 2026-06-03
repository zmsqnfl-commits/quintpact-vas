"""
VAS 2.4 무결점 10-Loop 통합 검증 스크립트
=========================================
10가지 다른 시나리오로 시스템 전체의 유기적 맞물림을 검증합니다.

검증 항목:
  1. HTML 구문 무결성 (모든 HTML 파일)
  2. CSS @import 체인 연결 검증
  3. JS 참조 무결성 (HTML에서 로드하는 JS 파일 존재 확인)
  4. 500줄 규칙 준수 (데이터 파일 예외)
  5. 데드 파일 감지 (어디서도 참조되지 않는 파일)
  6. 다국어 i18n 키 정합성 (ko/en 양쪽 모두 존재)
  7. 디자인 프리셋 12종 전수 검증 (design-controller.html)
  8. final/ 폴더 파일 무결성 (Security만 쓰기)
  9. 폰트 폴백 안전성 검증 (Pretendard 보장)
  10. 크로스 레퍼런스 검증 (GEMINI/HANDOFF/docs 문서 참조 무결성)
"""
import os
import re
import json
import sys
import io
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
        RESULTS.append(f"  [FAIL] {name} — {detail}")

def read_file(path):
    """UTF-8로 파일 읽기 (한국어 파일 안전)"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return f.read()

def get_html_files():
    """모든 HTML 파일 경로 목록 (BASE 기준 상대 경로)"""
    files = []
    if os.path.exists(os.path.join(BASE, 'src', 'vas-hub.html')):
        files.append('src/vas-hub.html')
    src_dir = os.path.join(BASE, 'src')
    if os.path.exists(src_dir):
        for f in os.listdir(src_dir):
            if f.endswith('.html') and os.path.isfile(os.path.join(src_dir, f)):
                files.append(os.path.join('src', f))
    return files

def get_src_files(ext):
    """src 디렉토리에서 특정 확장자 파일 목록 (BASE 기준 상대 경로)"""
    src_dir = os.path.join(BASE, 'src')
    if not os.path.exists(src_dir):
        return []
    return [os.path.join('src', f) for f in os.listdir(src_dir)
            if f.endswith(ext) and os.path.isfile(os.path.join(src_dir, f))]


# ============================================================
# LOOP 1: HTML 구문 무결성
# ============================================================
print("=" * 60)
print("LOOP 1/10: HTML 구문 무결성")
print("=" * 60)

html_files = get_html_files()
for hf in html_files:
    content = read_file(os.path.join(BASE, hf))
    has_doctype = '<!DOCTYPE' in content or '<!doctype' in content
    has_html_close = '</html>' in content
    has_head = '<head>' in content or '<head ' in content
    has_body = '<body>' in content or '<body ' in content
    check(f"{hf} DOCTYPE", has_doctype, "DOCTYPE 선언 누락")
    check(f"{hf} </html>", has_html_close, "HTML 닫기 태그 누락")
    check(f"{hf} <head>", has_head, "HEAD 태그 누락")
    check(f"{hf} <body>", has_body, "BODY 태그 누락")
    # meta charset
    has_charset = 'charset' in content.lower()
    check(f"{hf} charset", has_charset, "charset 메타태그 누락")

# ============================================================
# LOOP 2: CSS @import 체인 연결 검증
# ============================================================
print("=" * 60)
print("LOOP 2/10: CSS @import 체인 연결 검증")
print("=" * 60)

css_files = get_src_files('.css')
for cf in css_files:
    content = read_file(os.path.join(BASE, cf))
    # 로컬 @import 찾기
    local_imports = re.findall(r"@import\s+url\(['\"]([^'\"]+)['\"]", content)
    for imp in local_imports:
        if imp.startswith('http'):
            continue  # CDN은 건너뜀
        imp_path = os.path.join(os.path.dirname(os.path.join(BASE, cf)), imp)
        check(f"{cf} → @import {imp}", os.path.exists(imp_path), f"파일 없음: {imp}")

# ============================================================
# LOOP 3: JS 참조 무결성
# ============================================================
print("=" * 60)
print("LOOP 3/10: JS 참조 무결성 (HTML→JS 연결)")
print("=" * 60)

for hf in html_files:
    content = read_file(os.path.join(BASE, hf))
    js_refs = re.findall(r'<script\s+src="([^"]+)"', content)
    for js in js_refs:
        if js.startswith('http'):
            continue
        js_path = os.path.join(os.path.dirname(os.path.join(BASE, hf)), js)
        check(f"{hf} → {js}", os.path.exists(js_path), f"JS 파일 없음: {js}")

# ============================================================
# LOOP 4: 500줄 규칙 준수
# ============================================================
print("=" * 60)
print("LOOP 4/10: 500줄 규칙 준수")
print("=" * 60)

code_files = html_files + css_files + get_src_files('.js')
DATA_EXCEPTIONS = ['slide-styles-data.js']  # 데이터 전용 파일 예외

for cf in code_files:
    base_name = os.path.basename(cf)
    if base_name in DATA_EXCEPTIONS:
        continue
    content = read_file(os.path.join(BASE, cf))
    line_count = len(content.splitlines())
    check(f"{cf} ({line_count}줄)", line_count <= 500, f"{line_count}줄 > 500줄 제한 초과")

# ============================================================
# LOOP 5: 데드 파일 감지
# ============================================================
print("=" * 60)
print("LOOP 5/10: 데드 파일 감지 (JS/CSS)")
print("=" * 60)

# 모든 HTML 파일의 내용을 합침
all_html_content = ""
for hf in html_files:
    all_html_content += read_file(os.path.join(BASE, hf))

# 모든 CSS 파일의 @import도 확인
all_css_content = ""
for cf in css_files:
    all_css_content += read_file(os.path.join(BASE, cf))

js_files = get_src_files('.js')
for jf in js_files:
    base_name = os.path.basename(jf)
    # HTML에서 직접 참조되거나 CSS에서 import되거나
    is_referenced = base_name in all_html_content or base_name in all_css_content
    check(f"{jf} 참조됨", is_referenced, f"어디에서도 로드되지 않는 데드 파일")

for cf in css_files:
    base_name = os.path.basename(cf)
    is_referenced = base_name in all_html_content or base_name in all_css_content
    check(f"{cf} 참조됨", is_referenced, f"어디에서도 로드되지 않는 데드 CSS")


# ============================================================
# LOOP 6: i18n 키 정합성
# ============================================================
print("=" * 60)
print("LOOP 6/10: 다국어 i18n 키 정합성")
print("=" * 60)

i18n_path = os.path.join(BASE, 'src', 'client-i18n.js')
if os.path.exists(i18n_path):
    i18n_content = read_file(i18n_path)
    # 줄 단위로 key: "value" 패턴만 추출 (value 내부 단어는 무시)
    ko_keys = set()
    en_keys = set()
    current_lang = None
    for line in i18n_content.splitlines():
        stripped = line.strip()
        if stripped.startswith('ko:'):
            current_lang = 'ko'
        elif stripped.startswith('en:'):
            current_lang = 'en'
        elif stripped.startswith('};') or stripped == '}':
            current_lang = None
        elif current_lang:
            # key: "value" 또는 key: 'value' 패턴
            m = re.match(r'^(\w+)\s*:', stripped)
            if m:
                if current_lang == 'ko':
                    ko_keys.add(m.group(1))
                else:
                    en_keys.add(m.group(1))

    if ko_keys and en_keys:
        missing_in_en = ko_keys - en_keys
        missing_in_ko = en_keys - ko_keys

        check("i18n ko->en completeness", len(missing_in_en) == 0,
              f"EN missing: {missing_in_en}" if missing_in_en else "")
        check("i18n en->ko completeness", len(missing_in_ko) == 0,
              f"KO missing: {missing_in_ko}" if missing_in_ko else "")
    else:
        check("i18n parsing", False, "ko/en block parsing failed")


# ============================================================
# LOOP 7: 디자인 프리셋 12종 전수 검증
# ============================================================
print("=" * 60)
print("LOOP 7/10: 디자인 프리셋 12종 전수 검증")
print("=" * 60)

EXPECTED_PRESETS = [
    'vercel', 'linear', 'stripe', 'apple', 'google',
    'neobrutal', 'untitled', 'shadcn', 'glow', 'ant', 'carbon', 'awwwards'
]

dc_path = os.path.join(BASE, 'src', 'design-controller.html')
preset_path = os.path.join(BASE, 'src', 'design-presets.js')

if os.path.exists(dc_path) and os.path.exists(preset_path):
    dc_content = read_file(dc_path)
    preset_content = read_file(preset_path)
    for preset in EXPECTED_PRESETS:
        # PRESETS 객체에 키가 존재하는지 (design-presets.js 확인)
        has_preset_def = f"'{preset}'" in preset_content or f'"{preset}"' in preset_content or f'{preset}:' in preset_content
        # 버튼에서 호출하는지 (design-controller.html에서 동적 생성됨 - 정적 검사 생략)
        check(f"프리셋 '{preset}' 정의", has_preset_def, "PRESETS 객체에 키 없음")
    
    # 각 프리셋에 prompt 필드 있는지 (design-presets.js 확인)
    preset_prompts = re.findall(r"prompt:\s*\"", preset_content)
    check(f"프리셋 prompt 필드 ({len(preset_prompts)}개)", len(preset_prompts) >= 12,
          f"프롬프트 {len(preset_prompts)}개 < 12개")

# ============================================================
# LOOP 8: final/ 폴더 무결성
# ============================================================
print("=" * 60)
print("LOOP 8/10: final/ 폴더 무결성")
print("=" * 60)

final_dir = os.path.join(BASE, 'final')
if os.path.exists(final_dir):
    check("final/ 폴더 존재", True)
    
    # final/ 내 HTML 파일 구문 검증 (재귀적 탐색)
    final_htmls = []
    for root, dirs, files in os.walk(final_dir):
        for f in files:
            if f.endswith('.html'):
                final_htmls.append(os.path.join(root, f))
    
    check("final/ 비어있지 않음", len(final_htmls) > 0 or len(os.listdir(final_dir)) > 0, "final/ 폴더가 비어있음")
    
    for fh_path in final_htmls:
        content = read_file(fh_path)
        has_close = '</html>' in content
        rel_fh = os.path.relpath(fh_path, final_dir)
        check(f"final/{rel_fh} 구문", has_close, "HTML 닫기 태그 누락")
    
    # final/ 내 MD 문서 존재 확인 (재귀적 탐색)
    final_mds = []
    for root, dirs, files in os.walk(final_dir):
        for f in files:
            if f.endswith('.md'):
                final_mds.append(os.path.join(root, f))
    check(f"final/ MD 문서 ({len(final_mds)}개)", len(final_mds) >= 1, "MD 문서 없음")
    
    # 루트 및 하위(src, docs, scripts) 폴더의 대상 파일 수집하여 final과 바이트 크기 비교 검증
    sync_targets = []
    # 1. Root
    for f in os.listdir(BASE):
        if os.path.isfile(os.path.join(BASE, f)) and f.endswith(('.html', '.css', '.js', '.py', '.md', '.bat')):
            sync_targets.append(f)
    # 2. Subdirectories
    for sub in ['src', 'docs', 'scripts']:
        sub_path = os.path.join(BASE, sub)
        if os.path.exists(sub_path):
            for f in os.listdir(sub_path):
                if os.path.isfile(os.path.join(sub_path, f)) and f.endswith(('.html', '.css', '.js', '.py', '.md', '.bat')):
                    sync_targets.append(os.path.join(sub, f))
                    
    for sf in sync_targets:
        root_file_path = os.path.join(BASE, sf)
        final_file_path = os.path.join(final_dir, sf)
        exists_in_final = os.path.exists(final_file_path)
        check(f"final/{sf} 존재", exists_in_final, f"final/{sf} 파일 누락")
        if exists_in_final:
            root_size = os.path.getsize(root_file_path)
            final_size = os.path.getsize(final_file_path)
            check(f"동기화 {sf} (root={root_size}B)", root_size == final_size,
                  f"크기 불일치: root={root_size}B vs final={final_size}B")
else:
    check("final/ 폴더 존재", False, "final/ 디렉토리 없음")


# ============================================================
# LOOP 9: 폰트 폴백 안전성 검증
# ============================================================
print("=" * 60)
print("LOOP 9/10: 폰트 폴백 안전성 (Pretendard 보장)")
print("=" * 60)

# 테마 적용 JS에서 Pretendard 폴백 로직 존재 확인
init_js = os.path.join(BASE, 'src', 'client-application-init.js')
if os.path.exists(init_js):
    init_content = read_file(init_js)
    has_geist_guard = 'Geist Mono' in init_content and 'Pretendard' in init_content
    check("init.js Geist Mono→Pretendard 폴백", has_geist_guard,
          "Geist Mono 사용 시 Pretendard 폴백 로직 없음")

# vas-hub.html 테마 적용에서도 확인
idx_path = os.path.join(BASE, 'src', 'vas-hub.html')
if os.path.exists(idx_path):
    idx_content = read_file(idx_path)
    has_idx_guard = 'Geist Mono' in idx_content and 'Pretendard' in idx_content
    check("vas-hub.html Pretendard 폴백", has_idx_guard,
          "vas-hub.html에 폰트 폴백 로직 없음")

# CSS에서 기본 body 폰트가 Pretendard인지
main_css = os.path.join(BASE, 'src', 'client-style.css')
if os.path.exists(main_css):
    css_content = read_file(main_css)
    has_pretendard_default = "Pretendard" in css_content and "font-family" in css_content
    check("client-style.css Pretendard 기본", has_pretendard_default,
          "body 기본 폰트가 Pretendard가 아님")

# design-controller의 프리셋에 Pretendard 폴백 있는지 (design-presets.js 확인)
preset_path = os.path.join(BASE, 'src', 'design-presets.js')
if os.path.exists(preset_path):
    preset_content = read_file(preset_path)
    # 모든 프리셋 font 필드에 Pretendard가 포함되는지
    font_fields = re.findall(r"font:\s*\"([^\"]+)\"", preset_content)
    all_have_pretendard = all('Pretendard' in f for f in font_fields)
    check(f"프리셋 폰트 ({len(font_fields)}개) Pretendard 포함",
          all_have_pretendard and len(font_fields) >= 12,
          f"Pretendard 없는 프리셋 발견")


# ============================================================
# LOOP 10: 크로스 레퍼런스 검증
# ============================================================
print("=" * 60)
print("LOOP 10/10: 크로스 레퍼런스 검증 (문서 참조 무결성)")
print("=" * 60)

# docs/index.md가 존재하는지
docs_index = os.path.join(BASE, 'docs', 'index.md')
check("docs/index.md 존재", os.path.exists(docs_index), "SSoT 문서 없음")

# docs/log.md가 존재하는지
docs_log = os.path.join(BASE, 'docs', 'log.md')
check("docs/log.md 존재", os.path.exists(docs_log), "연대기 문서 없음")

# docs/design-system.md가 존재하는지
docs_ds = os.path.join(BASE, 'docs', 'design-system.md')
check("docs/design-system.md 존재", os.path.exists(docs_ds), "디자인 시스템 명세 없음")

# CONTEXT.md에서 docs/index.md 참조하는지
gemini_path = os.path.join(BASE, '.agents', 'CONTEXT.md')
if os.path.exists(gemini_path):
    gemini_content = read_file(gemini_path)
    check("CONTEXT.md → docs/index.md 참조", 'docs/index.md' in gemini_content,
          "GEMINI에서 SSoT 참조 없음")
    check("CONTEXT.md → docs/log.md 참조", 'docs/log.md' in gemini_content,
          "GEMINI에서 로그 참조 없음")

# HANDOFF.md에서 docs 참조
handoff_path = os.path.join(BASE, 'docs', 'HANDOFF.md')
if os.path.exists(handoff_path):
    handoff_content = read_file(handoff_path)
    check("HANDOFF.md → docs/index.md 참조", 'docs/index.md' in handoff_content,
          "HANDOFF에서 SSoT 참조 없음")

# HANDOFF.md에 구버전 참조(HISTORY.md, LESSONS.md) 없는지
    has_old_ref = 'HISTORY.md' in handoff_content or 'LESSONS.md' in handoff_content
    check("HANDOFF.md 구버전 참조 없음", not has_old_ref,
          "HISTORY.md/LESSONS.md 구버전 참조 잔존")

# README.md에 구버전 HISTORY.md/LESSONS.md 파일 참조가 없는지 (폴더 다이어그램 제외)
readme_path = os.path.join(BASE, 'README.md')
if os.path.exists(readme_path):
    readme_content = read_file(readme_path)
    old_file_refs = readme_content.count('HISTORY.md')
    check(f"README.md HISTORY.md 잔존 ({old_file_refs}건)",
          old_file_refs == 0,
          f"HISTORY.md가 {old_file_refs}건 잔존")


# ============================================================
# 최종 결과
# ============================================================
print("\n" + "=" * 60)
print(f"  VAS 2.4 무결점 10-Loop 통합 검증 결과")
print("=" * 60)

for r in RESULTS:
    status = "[PASS]" if "[PASS]" in r else "[FAIL]"
    color = "" if status == "[PASS]" else ">>> "
    print(f"{color}{r}")

print("\n" + "-" * 60)
total = PASS + FAIL
print(f"  TOTAL: {total}건 | PASS: {PASS} | FAIL: {FAIL}")
print(f"  합격률: {PASS/total*100:.1f}%" if total > 0 else "  검증 항목 없음")

if FAIL == 0:
    print("\n  ★★★ 10전 10승 무결점 통과 (10/10) ★★★")
else:
    print(f"\n  ⚠️ {FAIL}건 실패 — 수정 후 재검증 필요")

print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
