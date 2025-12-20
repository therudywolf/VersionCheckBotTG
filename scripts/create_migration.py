#!/usr/bin/env python
"""Script to create a new migration."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.config import Config
from alembic import command

def main():
    """Create a new migration."""
    if len(sys.argv) < 2:
        print("Usage: python create_migration.py <message>")
        sys.exit(1)
    
    message = sys.argv[1]
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)

if __name__ == "__main__":
    main()

