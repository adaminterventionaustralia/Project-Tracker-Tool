#!/usr/bin/env python3
"""
compile-report.py — Compiles individual project reports into a single daily digest.

Reads all {ProjectName}_{date}.md files from the reports directory,
merges them into one summary document, and optionally sends via email.

Usage:
    python compile-report.py                           # compile today's reports
    python compile-report.py --date 2026-03-29         # compile for a specific date
    python compile-report.py --email you@example.com   # compile and email
    python compile-report.py --all                     # compile latest report per project (any date)
"""

import os
import re
import sys
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path


def find_reports(reports_dir: Path, target_date: str | None = None, use_all: bool = False) -> list[Path]:
    """Find matching report files."""
    pattern = re.compile(r'^(.+)_(\d{4}-\d{2}-\d{2})\.md$')
    reports = []

    for f in sorted(reports_dir.iterdir()):
        if not f.is_file():
            continue
        m = pattern.match(f.name)
        if not m:
            continue

        if use_all:
            reports.append(f)
        elif target_date:
            if m.group(2) == target_date:
                reports.append(f)
        else:
            # Default: today
            if m.group(2) == datetime.now().strftime('%Y-%m-%d'):
                reports.append(f)

    # If --all, keep only the latest per project
    if use_all:
        latest: dict[str, Path] = {}
        for f in reports:
            m = pattern.match(f.name)
            if m:
                name = m.group(1)
                if name not in latest or f.name > latest[name].name:
                    latest[name] = f
        reports = sorted(latest.values())

    return reports


def extract_section(content: str, heading: str) -> str | None:
    """Extract content under a specific ## heading."""
    pattern = rf'^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)'
    m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def compile_digest(reports: list[Path]) -> str:
    """Build the compiled daily digest."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    lines = []
    lines.append(f"# Daily Project Digest — {date_str}")
    lines.append(f"_Compiled: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append(f"_Projects scanned: {len(reports)}_")
    lines.append("")

    # ── Quick Summary Table ──
    lines.append("## Overview")
    lines.append("")
    lines.append("| Project | MVP Difficulty | Open Tasks | Last Commit |")
    lines.append("|---------|-----------------|------------|-------------|")

    summaries = []
    for rpt in reports:
        content = rpt.read_text(encoding='utf-8', errors='replace')

        # Extract project name from title
        title_match = re.search(r'^# Project Report: (.+)$', content, re.MULTILINE)
        project_name = title_match.group(1) if title_match else rpt.stem

        # MVP difficulty score
        difficulty_match = re.search(r'\*\*Score:\*\*\s*(\d+)/10', content)
        difficulty = difficulty_match.group(1) if difficulty_match else '—'

        # Count open tasks
        todo_match = re.search(r'Found \*\*(\d+)\*\* task marker', content)
        todo_count = todo_match.group(1) if todo_match else '0'

        # Last commit
        commit_match = re.search(r'\*\*Message:\*\*\s*(.+)', content)
        date_match = re.search(r'\*\*Date:\*\*\s*(.+)', content)
        if commit_match:
            last_commit = commit_match.group(1).strip()[:50]
            if date_match:
                last_commit += f" ({date_match.group(1).strip()[:10]})"
        else:
            last_commit = '—'

        lines.append(f"| {project_name} | {difficulty}/10 | {todo_count} | {last_commit} |")

        summaries.append({
            'name': project_name,
            'difficulty': difficulty,
            'todos': todo_count,
            'content': content,
        })

    lines.append("")

    # ── Action Items (all open tasks consolidated) ──
    lines.append("## Consolidated Action Items")
    lines.append("")
    has_todos = False
    for s in summaries:
        todo_section = extract_section(s['content'], 'Open Tasks')
        if todo_section and 'No TODO' not in todo_section:
            has_todos = True
            lines.append(f"### {s['name']}")
            # Re-indent the TODO items
            for line in todo_section.split('\n'):
                if line.startswith('Found **'):
                    continue
                if line.strip():
                    lines.append(line)
            lines.append("")

    if not has_todos:
        lines.append("_No open tasks across any project._")
        lines.append("")

    # ── Individual Reports ──
    lines.append("---")
    lines.append("## Individual Project Reports")
    lines.append("")
    for rpt in reports:
        content = rpt.read_text(encoding='utf-8', errors='replace')
        # Bump headings down by 1 level for nesting
        adjusted = re.sub(r'^(#+)', r'#\1', content, flags=re.MULTILINE)
        lines.append(adjusted)
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"_End of daily digest — {date_str}_")
    return '\n'.join(lines)


def send_email(subject: str, body: str, to_email: str):
    """Send the digest via email using SMTP (configured via env vars)."""
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')  # App password for Gmail
    from_email = os.environ.get('SMTP_FROM', smtp_user)

    if not smtp_user or not smtp_pass:
        print("Error: SMTP_USER and SMTP_PASS environment variables required for email.")
        print("For Gmail, use an App Password: https://myaccount.google.com/apppasswords")
        sys.exit(1)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    # Attach as plain text (markdown is readable as plain text)
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Email failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Compile project reports into a daily digest.')
    parser.add_argument('--reports-dir', '-d', type=str, default='.',
                        help='Directory containing individual reports')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file path (default: daily-digest_{date}.md)')
    parser.add_argument('--date', type=str, default=None,
                        help='Target date YYYY-MM-DD (default: today)')
    parser.add_argument('--all', action='store_true',
                        help='Compile latest report per project regardless of date')
    parser.add_argument('--email', '-e', type=str, default=None,
                        help='Email address to send the digest to')
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir).resolve()
    if not reports_dir.is_dir():
        print(f"Error: {reports_dir} is not a directory.")
        sys.exit(1)

    reports = find_reports(reports_dir, target_date=args.date, use_all=args.all)
    if not reports:
        date_label = args.date or datetime.now().strftime('%Y-%m-%d')
        print(f"No reports found for {date_label} in {reports_dir}")
        sys.exit(0)

    print(f"Found {len(reports)} report(s). Compiling digest...")
    digest = compile_digest(reports)

    # Save digest
    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    out_filename = args.output or f"daily-digest_{date_str}.md"
    out_path = Path(out_filename)
    out_path.write_text(digest, encoding='utf-8')
    print(f"Digest saved: {out_path}")

    # Also save a 'latest' copy for easy dashboard access
    latest_path = Path("daily-digest-latest.md")
    latest_path.write_text(digest, encoding='utf-8')
    print(f"Latest digest copied to: {latest_path}")

    # Email if requested
    if args.email:
        subject = f"Daily Project Digest — {date_str}"
        send_email(subject, digest, args.email)


if __name__ == '__main__':
    main()
