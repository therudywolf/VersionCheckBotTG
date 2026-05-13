#!/usr/bin/env python3
"""
Add AGPL v3 license headers to Python files.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import os
import re
from pathlib import Path

LICENSE_HEADER = '''"""
VersionCheckBot - Telegram bot for monitoring software versions and CVE vulnerabilities

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors
"""
'''

def has_license_header(content: str) -> bool:
    """Check if file already has a license header."""
    return "SPDX-License-Identifier" in content or "AGPL" in content[:500]


def add_license_header(file_path: Path) -> bool:
    """Add license header to a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if has_license_header(content):
            print(f"✓ {file_path.relative_to('.')}: Already has license header")
            return False

        # Skip shebang if it exists
        if content.startswith('#!'):
            lines = content.split('\n')
            shebang = lines[0]
            rest = '\n'.join(lines[1:])
            new_content = shebang + '\n' + LICENSE_HEADER + rest
        else:
            new_content = LICENSE_HEADER + content

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✓ {file_path.relative_to('.')}: Added license header")
        return True

    except Exception as e:
        print(f"✗ {file_path.relative_to('.')}: Error - {e}")
        return False


def main():
    """Add license headers to all Python files."""
    root = Path('.')
    py_files = list(root.glob('bot/**/*.py')) + list(root.glob('tests/**/*.py')) + [root / 'bot.py', root / 'config.py']
    py_files = [f for f in py_files if f.is_file() and '__pycache__' not in str(f)]

    print(f"Processing {len(py_files)} Python files...")
    print()

    modified = 0
    for py_file in sorted(py_files):
        if add_license_header(py_file):
            modified += 1

    print()
    print(f"Summary: {modified} files modified, {len(py_files) - modified} unchanged")


if __name__ == '__main__':
    main()
