#!/usr/bin/env python3
"""
tidy.py — Moves dated scan reports into Archive/YYYY-MM-DD/ subdirectories.

Matches files named: {anything}_{YYYY-MM-DD}.md
Leaves undated files (dashboard.md, README.md, etc.) in place.

Usage:
    python tidy.py              # tidy current directory
    python tidy.py --dry-run    # preview without moving
    python tidy.py --all        # include today's files (default: skip today)
"""

import re
import shutil
import argparse
from datetime import date
from pathlib import Path

DATE_PATTERN = re.compile(r'^.+_(\d{4}-\d{2}-\d{2})\.md$')


def main():
    parser = argparse.ArgumentParser(description='Archive dated scan reports.')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Preview moves without actually doing anything')
    parser.add_argument('--all', '-a', action='store_true',
                        help="Include today's files (default: skip them)")
    args = parser.parse_args()

    here = Path(__file__).parent
    archive = here / 'Archive'
    today = date.today().isoformat()

    candidates = []
    for f in sorted(here.glob('*.md')):
        m = DATE_PATTERN.match(f.name)
        if not m:
            continue
        file_date = m.group(1)
        if file_date == today and not args.all:
            continue
        candidates.append((f, file_date))

    if not candidates:
        print("Nothing to archive.")
        return

    moved = 0
    for src, file_date in candidates:
        dest_dir = archive / file_date
        dest = dest_dir / src.name

        if dest.exists():
            print(f"  SKIP (exists): {src.name}")
            continue

        if args.dry_run:
            print(f"  [dry-run] {src.name} -> Archive/{file_date}/")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            print(f"  Moved: {src.name} -> Archive/{file_date}/")
        moved += 1

    action = "Would move" if args.dry_run else "Moved"
    print(f"\n{action} {moved} file(s).")


if __name__ == '__main__':
    main()
