#!/usr/bin/env python
"""Script to restore database from backup."""
import sys
import os
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


def main():
    """Restore database from backup."""
    if len(sys.argv) < 2:
        print("Usage: python restore_backup.py <backup_file>")
        print("Example: python restore_backup.py backups/bot_backup_20240101_120000.db")
        sys.exit(1)
    
    backup_file = Path(sys.argv[1])
    
    if not backup_file.exists():
        print(f"Error: Backup file not found: {backup_file}")
        sys.exit(1)
    
    # Get database path from config
    db_url = settings.DATABASE_URL
    if not db_url.startswith("sqlite:///"):
        print("Error: Restore script only supports SQLite databases")
        sys.exit(1)
    
    db_path = Path(db_url.replace("sqlite:///", ""))
    
    # Create backup of current database if it exists
    if db_path.exists():
        current_backup = db_path.parent / f"{db_path.name}.pre_restore"
        shutil.copy2(db_path, current_backup)
        print(f"Created backup of current database: {current_backup}")
    
    # Restore from backup
    try:
        shutil.copy2(backup_file, db_path)
        print(f"✅ Database restored from: {backup_file}")
        print(f"Database path: {db_path.absolute()}")
    except Exception as e:
        print(f"Error restoring database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

