#!/usr/bin/env python3
"""
project-scan.py — Drop into any project folder and run it.
Analyzes the project structure, README, TODOs, git status, and produces
a markdown report: {ProjectName}_{YYYY-MM-DD}.md

Usage:
    python project-scan.py                  # scans current directory, outputs to current directory
    python project-scan.py --output /path   # scans current directory, outputs to specified path
    python project-scan.py --repo /path     # scans current directory, copies report into a git repo and commits
"""

import os
import sys
import re
import subprocess
import argparse
import json
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────
TODO_PATTERNS = [
    r'#\s*TODO\b',
    r'#\s*FIXME\b',
    r'#\s*HACK\b',
    r'#\s*XXX\b',
    r'//\s*TODO\b',
    r'//\s*FIXME\b',
    r'/\*\s*TODO\b',
]

SCAN_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
    '.java', '.cs', '.cpp', '.c', '.h', '.go', '.rs', '.rb', '.php',
    '.yaml', '.yml', '.toml', '.json', '.xml', '.sh', '.bat', '.ps1',
    '.md', '.txt', '.env', '.cfg', '.ini',
}

IGNORE_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
    '.next', 'dist', 'build', '.cache', '.tox', 'target', 'bin', 'obj',
    '.idea', '.vscode', '.vs', 'coverage', '.nyc_output', '.turbo',
    'source', 'vendor', 'third_party', 'external', 'logs', 'tmp', 'temp',
    'dist-ssr', 'out',
}

MAX_FILE_SCAN_SIZE = 100_000  # bytes — skip huge files for TODO scanning


# ──────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────

def run_cmd(cmd: list[str], cwd: str | None = None) -> str | None:
    """Run a command and return stdout, or None on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def detect_project_name(project_dir: Path) -> str:
    """Try to pull the project name from package.json, pyproject.toml, Cargo.toml, or folder name."""
    # package.json
    pkg = project_dir / 'package.json'
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding='utf-8', errors='replace'))
            if data.get('name'):
                return data['name']
        except Exception:
            pass

    # pyproject.toml
    pyproj = project_dir / 'pyproject.toml'
    if pyproj.exists():
        try:
            text = pyproj.read_text(encoding='utf-8', errors='replace')
            m = re.search(r'name\s*=\s*"([^"]+)"', text)
            if m:
                return m.group(1)
        except Exception:
            pass

    # Cargo.toml
    cargo = project_dir / 'Cargo.toml'
    if cargo.exists():
        try:
            text = cargo.read_text(encoding='utf-8', errors='replace')
            m = re.search(r'name\s*=\s*"([^"]+)"', text)
            if m:
                return m.group(1)
        except Exception:
            pass

    return project_dir.resolve().name


def extract_readme_summary(project_dir: Path) -> str:
    """Pull the first meaningful paragraph from README as the project intent."""
    for name in ['README.md', 'README.rst', 'README.txt', 'README']:
        readme = project_dir / name
        if readme.exists():
            try:
                text = readme.read_text(encoding='utf-8', errors='replace')
                lines = text.split('\n')
                # Skip title lines (# heading or === underline)
                summary_lines = []
                past_title = False
                for line in lines:
                    stripped = line.strip()
                    if not past_title:
                        if stripped.startswith('#') or re.match(r'^[=\-]+$', stripped) or stripped == '':
                            continue
                        past_title = True
                    if past_title:
                        if stripped == '' and summary_lines:
                            break  # end of first paragraph
                        if stripped:
                            summary_lines.append(stripped)
                if summary_lines:
                    return ' '.join(summary_lines)[:500]
            except Exception:
                pass
    return '_No README found — consider adding one._'


def get_package_description(project_dir: Path) -> str | None:
    """Try to get description from package.json or pyproject.toml."""
    pkg = project_dir / 'package.json'
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding='utf-8', errors='replace'))
            if data.get('description'):
                return data['description']
        except Exception:
            pass

    pyproj = project_dir / 'pyproject.toml'
    if pyproj.exists():
        try:
            text = pyproj.read_text(encoding='utf-8', errors='replace')
            m = re.search(r'description\s*=\s*"([^"]+)"', text)
            if m:
                return m.group(1)
        except Exception:
            pass
    return None


def get_git_info(project_dir: Path) -> dict:
    """Gather last commit message/date and total commit count."""
    info = {
        'is_git': False,
        'last_commit': None,
        'last_commit_date': None,
        'commit_count': 0,
    }

    if not (project_dir / '.git').exists():
        return info

    info['is_git'] = True
    cwd = str(project_dir)

    # Last commit
    log = run_cmd(['git', 'log', '-1', '--format=%s|||%ai'], cwd=cwd)
    if log and '|||' in log:
        parts = log.split('|||')
        info['last_commit'] = parts[0]
        info['last_commit_date'] = parts[1]

    count_str = run_cmd(['git', 'rev-list', '--count', 'HEAD'], cwd=cwd)
    if count_str and count_str.isdigit():
        info['commit_count'] = int(count_str)

    return info


def scan_todos(project_dir: Path) -> list[dict]:
    """Scan source files for TODO/FIXME/HACK comments."""
    todos = []
    combined_pattern = re.compile('|'.join(TODO_PATTERNS), re.IGNORECASE)

    for root, dirs, files in os.walk(project_dir):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in SCAN_EXTENSIONS:
                continue
            if fpath.stat().st_size > MAX_FILE_SCAN_SIZE:
                continue

            try:
                content = fpath.read_text(encoding='utf-8', errors='replace')
                for i, line in enumerate(content.split('\n'), 1):
                    if combined_pattern.search(line):
                        rel = fpath.relative_to(project_dir)
                        todos.append({
                            'file': str(rel),
                            'line': i,
                            'text': line.strip()[:200],
                        })
            except Exception:
                continue

    return todos


def estimate_mvp_difficulty(project_dir: Path, git_info: dict, todos: list[dict]) -> tuple[int, list[str]]:
    """Heuristic 1-10 estimate of how much work remains to reach MVP (1 = easy/close, 10 = hard/far)."""
    has_tests = any([
        (project_dir / 'tests').exists(),
        (project_dir / 'test').exists(),
        (project_dir / '__tests__').exists(),
        (project_dir / 'spec').exists(),
    ])
    has_readme = any((project_dir / r).exists() for r in ['README.md', 'README.rst', 'README.txt'])
    has_lock = any((project_dir / f).exists() for f in [
        'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
        'Pipfile.lock', 'poetry.lock', 'Cargo.lock'
    ])

    score = 10
    reasons = []
    commit_count = git_info['commit_count']

    if commit_count == 0:
        reasons.append("no commits yet")
    elif commit_count < 5:
        score -= 1
    elif commit_count < 20:
        score -= 2
    elif commit_count < 50:
        score -= 3
    else:
        score -= 4
        reasons.append(f"mature history ({commit_count} commits)")

    if has_readme:
        score -= 1
    else:
        reasons.append("no README")

    if has_lock:
        score -= 1
    else:
        reasons.append("no dependency lockfile")

    if has_tests:
        score -= 1
    else:
        reasons.append("no test suite")

    todo_count = len(todos)
    if todo_count == 0:
        score -= 1
    elif todo_count > 20:
        score += 2
        reasons.append(f"{todo_count} open task markers")
    elif todo_count > 10:
        score += 1
        reasons.append(f"{todo_count} open task markers")

    score = max(1, min(10, score))
    return score, reasons


# ──────────────────────────────────────────────────────────────────────
# REPORT GENERATION
# ──────────────────────────────────────────────────────────────────────

def generate_report(project_dir: Path) -> tuple[str, str]:
    """Generate the markdown report. Returns (filename, content)."""
    project_name = detect_project_name(project_dir)
    date_str = datetime.now().strftime('%Y-%m-%d')
    safe_name = re.sub(r'[^\w\-.]', '_', project_name)
    filename = f"{safe_name}_{date_str}.md"

    readme_summary = extract_readme_summary(project_dir)
    pkg_desc = get_package_description(project_dir)
    git_info = get_git_info(project_dir)
    todos = scan_todos(project_dir)
    difficulty, difficulty_reasons = estimate_mvp_difficulty(project_dir, git_info, todos)

    # Build report
    lines = []
    lines.append(f"# Project Report: {project_name}")
    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append(f"_Path: `{project_dir.resolve()}`_")
    lines.append("")

    # ── Project Purpose ──
    lines.append("## Project Purpose")
    lines.append(pkg_desc if pkg_desc else readme_summary)
    lines.append("")

    # ── Open Tasks (TODOs) ──
    lines.append("## Open Tasks")
    if todos:
        lines.append(f"Found **{len(todos)}** task marker(s):")
        lines.append("")
        # Group by file
        by_file: dict[str, list] = {}
        for t in todos:
            by_file.setdefault(t['file'], []).append(t)
        for fpath, items in sorted(by_file.items()):
            lines.append(f"### `{fpath}`")
            for item in items:
                lines.append(f"- **Line {item['line']}:** `{item['text']}`")
            lines.append("")
    else:
        lines.append("_No TODO/FIXME/HACK markers found in source files._")
        lines.append("")

    # ── Last Commit ──
    lines.append("## Last Commit")
    if git_info['is_git'] and git_info['last_commit']:
        lines.append(f"**Message:** {git_info['last_commit']}")
        lines.append(f"**Date:** {git_info['last_commit_date']}")
    else:
        lines.append("_No commits found (not a git repo, or no commits yet)._")
    lines.append("")

    # ── MVP Difficulty ──
    lines.append("## MVP Difficulty")
    lines.append(f"**Score:** {difficulty}/10")
    if difficulty_reasons:
        lines.append(f"**Why:** {'; '.join(difficulty_reasons)}")
    lines.append("")

    lines.append("---")
    lines.append(f"_Report generated by project-scan.py_")

    return filename, '\n'.join(lines)


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Scan a project folder and generate a status report.')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Directory to save the report (default: current directory)')
    parser.add_argument('--repo', '-r', type=str, default=None,
                        help='Git repo path to copy report into and auto-commit')
    parser.add_argument('--dir', '-d', type=str, default='.',
                        help='Project directory to scan (default: current directory)')
    args = parser.parse_args()

    project_dir = Path(args.dir).resolve()
    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory.")
        sys.exit(1)

    print(f"Scanning: {project_dir}")
    filename, content = generate_report(project_dir)

    # Determine output location
    if args.repo:
        out_dir = Path(args.repo).resolve()
    elif args.output:
        out_dir = Path(args.output).resolve()
    else:
        out_dir = Path.cwd()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(content, encoding='utf-8')
    print(f"Report saved: {out_path}")

    # If repo mode, git add + commit
    if args.repo:
        repo_dir = Path(args.repo).resolve()
        run_cmd(['git', 'add', filename], cwd=str(repo_dir))
        run_cmd(['git', 'commit', '-m', f'Report: {filename}'], cwd=str(repo_dir))
        print(f"Committed to repo: {repo_dir}")


if __name__ == '__main__':
    main()
