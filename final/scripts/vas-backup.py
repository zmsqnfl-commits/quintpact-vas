import os
import datetime
import shutil
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def create_backup():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, '..'))
    backup_dir = os.path.join(base_dir, '.vas_backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    target_zip = os.path.join(backup_dir, f'checkpoint_{timestamp}')
    
    # Prune old backups (keep only last 10 to save space)
    existing_backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.zip')])
    while len(existing_backups) >= 10:
        oldest = existing_backups.pop(0)
        os.remove(os.path.join(backup_dir, oldest))
        print(f"Removed old backup: {oldest}")

    print("Creating Project Root Checkpoint...")
    
    # Ignore patterns
    def ignore_patterns(path, names):
        return [n for n in names if n in ('.vas_backups', '.git', 'node_modules', '__pycache__', '.vscode', '.idea')]
    
    # Create temp directory for safe zipping
    temp_dir = os.path.join(backup_dir, 'temp_copy')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        
    try:
        shutil.copytree(base_dir, temp_dir, ignore=ignore_patterns)
        shutil.make_archive(target_zip, 'zip', temp_dir)
        print(f"✅ Vibe Coding Checkpoint Saved: .vas_backups/checkpoint_{timestamp}.zip")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    create_backup()
