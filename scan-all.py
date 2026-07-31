#!/usr/bin/env python3
"""
scan-all.py — Batch runner. Auto-discovers sibling project folders
(everything one level above this tool's own directory) and scans each
one, saving reports to the reports repo.

Usage:
    python scan-all.py                    # discover + scan sibling folders
    python scan-all.py --root /path       # scan siblings of a different folder
    python scan-all.py --exclude "Archive" --exclude "Old Stuff"
    python scan-all.py --push             # git push after committing
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Folders that are never projects, even if found alongside real ones.
IGNORE_NAMES = {
    '$RECYCLE.BIN', 'System Volume Information', 'node_modules', '.git',
}


def run_cmd(cmd: list[str], cwd: str | None = None) -> bool:
    """Run a command, return True on success."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
        if result.returncode != 0 and result.stderr:
            print(f"  Warning: {result.stderr.strip()[:200]}")
        return result.returncode == 0
    except Exception as e:
        print(f"  Error: {e}")
        return False


def has_harness(project: Path) -> bool:
    """A project already has the AI harness if it has both CLAUDE.md and .ai/context.json."""
    return (project / 'CLAUDE.md').exists() and (project / '.ai' / 'context.json').exists()


def install_harness(installer: Path, project: Path) -> bool:
    """Run AIHarness/install.ps1 against a project missing the harness."""
    cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
           '-File', str(installer), '-Path', str(project)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        for line in result.stdout.splitlines():
            print(f"    {line}")
        if result.returncode != 0:
            print(f"    Harness install failed: {result.stderr.strip()[:200]}")
            return False
        return True
    except Exception as e:
        print(f"    Harness install error: {e}")
        return False


def discover_projects(root: Path, tool_dir: Path, exclude: set[str]) -> list[Path]:
    """Find candidate project folders: immediate subdirectories of root,
    excluding this tool's own folder, hidden folders, and known non-project names."""
    projects = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.resolve() == tool_dir.resolve():
            continue
        if entry.name.startswith('.'):
            continue
        if entry.name in IGNORE_NAMES or entry.name in exclude:
            continue
        projects.append(entry)
    return projects


def main():
    parser = argparse.ArgumentParser(description='Batch-scan all sibling projects.')
    parser.add_argument('--root', type=str, default=None,
                        help='Folder to scan for projects (default: parent of this tool\'s folder)')
    parser.add_argument('--exclude', action='append', default=[],
                        help='Folder name to skip (repeatable)')
    parser.add_argument('--repo', '-r', type=str, default='./reports',
                        help='Reports git repo directory')
    parser.add_argument('--push', action='store_true',
                        help='Git push after committing all reports')
    parser.add_argument('--skip-harness', action='store_true',
                        help='Do not install the AI harness into projects missing it')
    args = parser.parse_args()

    tool_dir = Path(__file__).resolve().parent
    root = Path(args.root).resolve() if args.root else tool_dir.parent
    if not root.is_dir():
        print(f"Root not found: {root}")
        sys.exit(1)

    repo_dir = Path(args.repo).resolve()
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Init reports repo if needed
    if not (repo_dir / '.git').exists():
        print(f"Initializing git repo at {repo_dir}")
        run_cmd(['git', 'init'], cwd=str(repo_dir))

    # Discover project folders
    projects = discover_projects(root, tool_dir, set(args.exclude))

    if not projects:
        print(f"No project folders found under {root}.")
        sys.exit(0)

    # Install the AI harness into any sibling project that doesn't have it yet.
    if not args.skip_harness:
        installer = root / 'AIHarness' / 'install.ps1'
        if installer.exists():
            missing = [p for p in projects if not has_harness(p)]
            if missing:
                print(f"Installing AI harness into {len(missing)} project(s) missing it...")
                for proj in missing:
                    print(f"  Harness: {proj.name}")
                    install_harness(installer, proj)
        else:
            print(f"Skipping harness install: {installer} not found")

    # Locate project-scan.py (same directory as this script)
    scanner = Path(__file__).parent / 'project-scan.py'
    if not scanner.exists():
        print(f"Error: project-scan.py not found at {scanner}")
        sys.exit(1)

    # Scan each project
    print(f"Scanning {len(projects)} project(s) under {root}...")
    print(f"Reports -> {repo_dir}")
    print("=" * 60)

    success = 0
    failed = 0
    for proj in projects:
        print(f"\n  Scanning: {proj.name}")
        cmd = [sys.executable, str(scanner), '--dir', str(proj), '--repo', str(repo_dir)]
        if run_cmd(cmd):
            success += 1
        else:
            print(f"  FAILED: {proj}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Done: {success} scanned, {failed} failed")

    # Commit all at once
    date_str = datetime.now().strftime('%Y-%m-%d')
    run_cmd(['git', 'add', '.'], cwd=str(repo_dir))
    run_cmd(['git', 'commit', '-m', f'Daily scan: {date_str} ({success} projects)'], cwd=str(repo_dir))

    if args.push:
        print("Pushing to remote...")
        if run_cmd(['git', 'push'], cwd=str(repo_dir)):
            print("Pushed successfully.")
        else:
            print("Push failed - check remote config.")


if __name__ == '__main__':
    main()
