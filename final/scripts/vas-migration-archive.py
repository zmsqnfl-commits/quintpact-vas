"""
VAS 2.4 마이그레이션 아카이버
============================
원본 프로젝트를 스캔 → .temp data/에 ZIP 백업 → final/에 배치.

사용법:
  python vas-migration-archive.py <원본프로젝트경로>
  python vas-migration-archive.py <원본프로젝트경로> --delete-source
  python vas-migration-archive.py --dry-run <원본프로젝트경로>
"""
import os
import sys
import io
import shutil
import zipfile
import argparse
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DATA = os.path.join(BASE_DIR, '.temp data')
FINAL_DIR = os.path.join(BASE_DIR, 'final')

# VAS 인프라 파일명 — 충돌 시 final/project/ 서브폴더에 격리
VAS_INFRA_FILES = {
    'index.html', 'design-controller.html', 'design-controller.css',
    'client-application.html', 'client-application-init.js',
    'client-form.js', 'client-export.js', 'client-i18n.js',
    'client-style.css', 'client-components.css', 'client-print.css',
    'session-monitor.html', 'slide-styles.html', 'slide-styles-data.js',
    'vas-backup.py', 'vas-migration-archive.py',
    'CONTEXT.md', 'GEMINI.md', 'CLAUDE.md', '.cursorrules', '.windsurfrules', 'HANDOFF.md', 'INSTRUCTIONS.md', 'MIGRATION.md', 'README.md',
    'Run-VAS-System.bat', 'Run-VAS-Backup.bat',
}

# 무시할 폴더 패턴
IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.vscode', '.idea', '.vs'}


def scan_project(source_path):
    """원본 프로젝트를 스캔하여 정보를 반환합니다."""
    file_count = 0
    total_size = 0
    extensions = {}
    conflicts = []

    for root, dirs, files in os.walk(source_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            fp = os.path.join(root, f)
            file_count += 1
            size = os.path.getsize(fp)
            total_size += size
            ext = os.path.splitext(f)[1].lower() or '(없음)'
            extensions[ext] = extensions.get(ext, 0) + 1
            # VAS 인프라 충돌 체크 (루트 레벨만)
            rel = os.path.relpath(fp, source_path)
            if os.sep not in rel and f in VAS_INFRA_FILES:
                conflicts.append(f)

    # 스택 자동 감지
    stack_hints = []
    if '.py' in extensions:
        stack_hints.append('Python')
    if '.js' in extensions or '.ts' in extensions or '.tsx' in extensions:
        stack_hints.append('JavaScript/TypeScript')
    if '.php' in extensions:
        stack_hints.append('PHP')
    if '.html' in extensions:
        stack_hints.append('HTML')
    if '.java' in extensions:
        stack_hints.append('Java')

    return {
        'file_count': file_count,
        'total_size': total_size,
        'extensions': dict(sorted(extensions.items(), key=lambda x: -x[1])),
        'conflicts': conflicts,
        'stack': ', '.join(stack_hints) if stack_hints else '알 수 없음',
    }


def clean_old_backups():
    """기존 마이그레이션 백업을 삭제합니다 (최근 1개 정책)."""
    if not os.path.isdir(TEMP_DATA):
        return 0
    removed = 0
    for f in os.listdir(TEMP_DATA):
        if f.endswith('_backup.zip'):
            os.remove(os.path.join(TEMP_DATA, f))
            print(f"  기존 백업 삭제: {f}")
            removed += 1
    return removed


def create_archive(source_path, project_name):
    """원본 프로젝트를 .temp data/프로젝트명_backup.zip으로 압축합니다."""
    os.makedirs(TEMP_DATA, exist_ok=True)
    zip_path = os.path.join(TEMP_DATA, f'{project_name}_backup.zip')

    archived_count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, source_path)
                zf.write(fp, arcname)
                archived_count += 1

    return zip_path, archived_count


def deploy_to_final(source_path, conflicts):
    """원본 프로젝트 파일을 final/에 복사합니다."""
    copied = 0
    for root, dirs, files in os.walk(source_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, source_path)
            # VAS 인프라 충돌 파일은 project/ 서브폴더에 격리
            if os.sep not in rel and f in VAS_INFRA_FILES:
                dest = os.path.join(FINAL_DIR, 'project', rel)
            else:
                dest = os.path.join(FINAL_DIR, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(fp, dest)
            copied += 1
    return copied


def main():
    parser = argparse.ArgumentParser(description='VAS 2.4 마이그레이션 아카이버')
    parser.add_argument('source', help='원본 프로젝트 경로')
    parser.add_argument('--delete-source', action='store_true',
                        help='아카이빙 후 원본 폴더 삭제')
    parser.add_argument('--dry-run', action='store_true',
                        help='스캔만 수행하고 실제 작업은 하지 않음')
    args = parser.parse_args()

    source = os.path.abspath(args.source)
    if not os.path.isdir(source):
        print(f"오류: '{source}' 폴더가 존재하지 않습니다.")
        sys.exit(1)

    project_name = os.path.basename(source)
    print(f"\n{'='*50}")
    print(f"  VAS 2.4 마이그레이션 아카이버")
    print(f"{'='*50}")
    print(f"  원본: {source}")
    print(f"  프로젝트명: {project_name}")

    # 1. 스캔
    print(f"\n[1/4] 프로젝트 스캔 중...")
    info = scan_project(source)
    size_mb = info['total_size'] / (1024 * 1024)
    print(f"  파일 수: {info['file_count']}개")
    print(f"  총 크기: {size_mb:.1f} MB")
    print(f"  감지 스택: {info['stack']}")
    print(f"  확장자 분포: {info['extensions']}")
    if info['conflicts']:
        print(f"  VAS 충돌 파일: {info['conflicts']} → final/project/에 격리됨")

    if args.dry_run:
        print(f"\n  [DRY-RUN] 스캔 완료. 실제 작업 없이 종료합니다.")
        sys.exit(0)

    # 2. 기존 백업 정리 (1개 정책)
    print(f"\n[2/4] 기존 마이그레이션 백업 정리...")
    removed = clean_old_backups()
    if removed == 0:
        print("  기존 백업 없음")

    # 3. ZIP 아카이브 생성
    print(f"\n[3/4] ZIP 아카이브 생성 중...")
    zip_path, archived = create_archive(source, project_name)
    zip_size = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  저장: {os.path.basename(zip_path)} ({zip_size:.1f} MB)")

    # ZIP 무결성 검증
    if archived != info['file_count']:
        print(f"  경고: 파일 수 불일치 (스캔={info['file_count']}, 압축={archived})")
        print(f"  원본 삭제가 차단됩니다.")
        args.delete_source = False
    else:
        print(f"  무결성 검증 통과 ({archived}개 파일)")

    # 4. final/ 에 배치
    print(f"\n[4/4] final/ 에 파일 배치 중...")
    copied = deploy_to_final(source, info['conflicts'])
    print(f"  배치 완료: {copied}개 파일")

    # 선택: 원본 삭제
    if args.delete_source:
        print(f"\n원본 폴더를 삭제합니다: {source}")
        confirm = input("  정말 삭제하시겠습니까? (y/N): ").strip().lower()
        if confirm == 'y':
            shutil.rmtree(source)
            print(f"  원본 폴더 삭제 완료.")
        else:
            print(f"  삭제 취소.")

    print(f"\n{'='*50}")
    print(f"  마이그레이션 아카이빙 완료!")
    print(f"  백업: .temp data/{project_name}_backup.zip")
    print(f"  배치: final/ ({copied}개 파일)")
    print(f"{'='*50}\n")


if __name__ == '__main__':
    main()
