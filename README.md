# Project Tracker Tool

Scans every project folder next to this tool (i.e. all sibling folders one level up from
wherever `Project Tracker Tool` itself lives) and builds an HTML dashboard covering, per
project: its purpose, open tasks, last commit, and an estimated difficulty to reach MVP.
No project list to maintain — new folders are picked up automatically.

Before scanning, it also makes sure every sibling project has the AI Harness context
protocol installed (`CLAUDE.md` + `.ai/`), installing it into any project that doesn't
have it yet. The harness is a separate companion tool that lives in its own folder next
to the projects — see [AI Harness auto-install](#ai-harness-auto-install) below. If you
don't use it, the step is skipped automatically (or opt out with `--skip-harness`).

## Files

| File | Purpose |
|------|---------|
| `scan-all.py` | **Entry point.** Auto-discovers sibling project folders and scans each one |
| `project-scan.py` | Per-project scanner (purpose, open tasks, last commit, MVP difficulty → markdown report) |
| `compile-report.py` | Compiles individual reports into one daily digest |
| `dashboard.py` | Renders the daily digest into an HTML dashboard |
| `tidy.py` | Archives dated reports into `Archive/YYYY-MM-DD/` |
| `scheduled.bat` | Runs the full pipeline end-to-end and pushes the results |

## Quick Start

```bash
cd "path/to/Project Tracker Tool"

# 1. Scan every sibling project folder, save reports to ./reports
python scan-all.py

# 2. Compile today's reports into a single digest
python compile-report.py --reports-dir reports

# 3. Turn the digest into an HTML dashboard (opens in browser)
python dashboard.py daily-digest-latest.md

# 4. Archive dated reports out of the way
python tidy.py
```

Or run the whole pipeline at once with `scheduled.bat`.

### Scanning somewhere else

```bash
python scan-all.py --root "D:\Some\Other\Folder"
python scan-all.py --exclude "Old Project" --exclude "Archive"
```

### AI Harness auto-install

Each `scan-all.py` run checks every discovered sibling project for `CLAUDE.md` and
`.ai/context.json`. Any project missing either gets the harness installed via
`AIHarness\install.ps1 -Path <project>` before scanning starts. The installer never
overwrites existing files, so this is safe to run on every scan — projects that already
have the harness are left untouched.

Requires a sibling `AIHarness/` folder (containing `install.ps1`) next to the discovered
projects; if it's not found, the step is skipped with a message. To opt out entirely:

```bash
python scan-all.py --skip-harness
```

## What Gets Scanned Live

Each project report has exactly four sections:

- **Project Purpose** — package/pyproject description, falling back to the first
  paragraph of the README
- **Open Tasks** — source code TODO/FIXME/HACK/XXX markers, grouped by file
- **Last Commit** — most recent commit message and date
- **MVP Difficulty** — a 1-10 heuristic estimate of remaining work (1 = close to MVP,
  10 = far from it), based on commit history, presence of a README/lockfile/test suite,
  and open task volume

## Ignored Directories

Per-project scans skip: `node_modules`, `.git`, `__pycache__`, `.venv`, `venv`, `env`,
`.next`, `dist`, `build`, `.cache`, `.tox`, `target`, `bin`, `obj`, `.idea`, `.vscode`,
`.vs`, `coverage`, `.nyc_output`, `.turbo`, `source`, `vendor`, `third_party`, `external`,
`logs`, `tmp`, `temp`, `dist-ssr`, `out`.

Sibling-folder discovery (`scan-all.py`) skips hidden folders (leading `.`), this tool's
own folder, and anything passed via `--exclude`.
