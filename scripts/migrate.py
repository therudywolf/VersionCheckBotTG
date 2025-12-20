#!/usr/bin/env python
"""Script to run database migrations."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.config import Config
from alembic import command

def main():
    """Run migrations."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

if __name__ == "__main__":
    main()

