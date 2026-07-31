#!/usr/bin/env python3
"""
dashboard.py — Premium HTML Project Dashboard Generator.

Parses the daily-digest_{date}.md produced by compile-report.py 
and generates a high-fidelity "Engineered Retro" HTML dashboard.
Inspired by the design of shawnos.ai.

Usage:
    python dashboard.py daily-digest_2026-04-02.md
"""

import os
import re
import sys
import argparse
import webbrowser
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# CONFIG & DESIGN TOKENS
# ──────────────────────────────────────────────────────────────────────

DESIGN = {
    'bg_color': '#FCFAF1',
    'bg_grid': 'rgba(0, 0, 0, 0.05)',
    'text_main': '#221E1A',
    'accent_terracotta': '#B45309',
    'accent_emerald': '#10B981',
    'border_color': 'rgba(34, 30, 26, 0.1)',
    'font_mono': "'JetBrains Mono', 'Fira Code', monospace",
}

# ──────────────────────────────────────────────────────────────────────
# PARSER
# ──────────────────────────────────────────────────────────────────────

class DigestParser:
    def __init__(self, file_path: Path):
        content = file_path.read_text(encoding='utf-8', errors='replace')
        self.content = content
        self.date = self._extract_date()
        self.projects = self._parse_projects()

    def _extract_date(self) -> str:
        m = re.search(r'Daily Project Digest — (\d{4}-\d{2}-\d{2})', self.content)
        return m.group(1) if m else datetime.now().strftime('%Y-%m-%d')

    def _parse_projects(self) -> list[dict]:
        # Individual reports are under "## Individual Project Reports"
        if "## Individual Project Reports" not in self.content:
            return []

        reports_section = self.content.split("## Individual Project Reports")[1]
        # Reports start with "## Project Report: {Name}"
        project_blocks = re.split(r'## Project Report:\s+', reports_section)[1:]

        projects = []
        for block in project_blocks:
            lines = block.strip().split('\n')
            name = lines[0].strip()

            # Simple metadata extraction
            path = self._regex_search(r'_Path:\s*`([^`]+)`', block, "Unknown Path")
            purpose = self._regex_search(r'### Project Purpose\s*\n(.+)', block, "No purpose found.")
            commit_msg = self._regex_search(r'\*\*Message:\*\*\s*(.+)', block, None)
            commit_date = self._regex_search(r'\*\*Date:\*\*\s*(.+)', block, None)
            difficulty = self._regex_search(r'\*\*Score:\*\*\s*(\d+)/10', block, "?")

            if commit_msg:
                last_commit = f"{commit_msg}" + (f" ({commit_date})" if commit_date else "")
            else:
                last_commit = "No commits found"

            # Extract Open Tasks
            todos = []
            if "### Open Tasks" in block:
                todo_section = block.split("### Open Tasks")[1].split("### Last Commit")[0].strip()
                if "No TODO/FIXME" not in todo_section:
                    # Look for lines starting with "- **Line"
                    todos = [line.strip().replace('- **', '').replace('**:', ':')
                            for line in todo_section.split('\n') if line.strip().startswith('-')]

            projects.append({
                'name': name,
                'id': re.sub(r'[^a-zA-Z0-9]', '-', name.lower()),
                'path': path,
                'purpose': purpose.strip(),
                'last_commit': last_commit,
                'difficulty': difficulty,
                'todos': todos,
            })
        return projects

    def _regex_search(self, pattern: str, text: str, default: str) -> str:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else default

# ──────────────────────────────────────────────────────────────────────
# HTML GENERATOR
# ──────────────────────────────────────────────────────────────────────

def generate_html(parser: DigestParser) -> str:
    # Build Project Cards
    cards_html = ""
    for p in parser.projects:
        todo_list = ""
        if p['todos']:
            todo_items = "".join([f"<li>{t}</li>" for t in p['todos'][:5]])
            if len(p['todos']) > 5:
                todo_items += f"<li class='more'>...and {len(p['todos']) - 5} more</li>"
            todo_list = f"<div class='section-label'>OPEN TASKS</div><ul class='todo-list'>{todo_items}</ul>"
        else:
            todo_list = "<div class='section-label'>OPEN TASKS</div><p class='none'>None</p>"

        cards_html += f"""
        <div class="project-card" id="{p['id']}">
            <div class="card-header">
                <div class="title-row">
                    <h2>{p['name']}</h2>
                </div>
                <div class="badge-row">
                    <span class="badge">MVP DIFFICULTY: {p['difficulty']}/10</span>
                </div>
            </div>

            <div class="card-body">
                <div class="intent-box">
                    <div class="section-label">PURPOSE</div>
                    <p>{p['purpose']}</p>
                </div>

                <div class="meta-grid">
                    <div class="meta-item">
                        <div class="section-label">LAST COMMIT</div>
                        <span>{p['last_commit']}</span>
                    </div>
                </div>

                <div class="activity-grid">
                    {todo_list}
                </div>
            </div>
        </div>
        """

    # Build Header Section
    sidebar_links = "".join([f'<li><a href="#{p["id"]}">{p["name"]}</a></li>' for p in parser.projects])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Digest — {parser.date}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #FCFAF1;
            --text: #221E1A;
            --accent: #B45309;
            --border: rgba(34, 30, 26, 0.1);
            --grid: rgba(0, 0, 0, 0.05);
            --card-bg: rgba(180, 83, 9, 0.03);
            --code-bg: rgba(0, 0, 0, 0.05);
            --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        body.dark-mode {{
            --bg: #0A0C10;
            --text: #D1D5DB;
            --accent: #4ADE80;
            --border: rgba(209, 213, 219, 0.1);
            --grid: rgba(255, 255, 255, 0.03);
            --card-bg: rgba(74, 222, 128, 0.05);
            --code-bg: rgba(255, 255, 255, 0.08);
        }}

        * {{ box-sizing: border-box; }}
        
        body {{
            margin: 0;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.5;
            background-image: 
                linear-gradient(var(--grid) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid) 1px, transparent 1px);
            background-size: 40px 40px;
            scroll-behavior: smooth;
            transition: background-color var(--transition), color var(--transition);
        }}

        header {{
            padding: 60px 40px;
            border-bottom: 1px solid var(--border);
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
        }}

        .theme-toggle {{
            position: absolute;
            top: 60px;
            right: 40px;
            background: var(--text);
            color: var(--bg);
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-family: inherit;
            font-size: 0.7rem;
            font-weight: 700;
            cursor: pointer;
            letter-spacing: 0.05em;
            transition: var(--transition);
        }}

        .theme-toggle:hover {{
            opacity: 0.8;
            transform: translateY(-1px);
        }}

        .header-meta {{
            font-size: 0.8rem;
            color: var(--accent);
            letter-spacing: 0.1em;
            font-weight: 700;
            margin-bottom: 8px;
        }}

        h1 {{
            margin: 0;
            font-size: 3rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 60px;
            padding: 40px;
        }}

        aside {{
            position: sticky;
            top: 40px;
            height: fit-content;
        }}

        aside ul {{
            list-style: none;
            padding: 0;
            margin: 0;
            border-top: 1px solid var(--border);
        }}

        aside li {{
            border-bottom: 1px solid var(--border);
        }}

        aside a {{
            display: block;
            padding: 12px 0;
            text-decoration: none;
            color: var(--text);
            font-size: 0.9rem;
            transition: all 0.2s;
        }}

        aside a:hover {{
            color: var(--accent);
            padding-left: 8px;
        }}

        .project-list {{
            display: flex;
            flex-direction: column;
            gap: 80px;
        }}

        .project-card {{
            scroll-margin-top: 40px;
        }}

        .sub-label {{
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 4px;
            display: block;
        }}

        .section-label {{
            font-size: 0.7rem;
            font-weight: 700;
            opacity: 0.5;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 8px;
        }}

        h2 {{
            margin: 0;
            font-size: 2rem;
            font-weight: 700;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            font-size: 0.75rem;
            font-weight: 700;
            border: 1px solid var(--accent);
            border-radius: 4px;
            margin-top: 12px;
            color: var(--accent);
            transition: var(--transition);
        }}

        .intent-box {{
            margin: 30px 0;
            padding: 20px;
            background: var(--card-bg);
            border-left: 2px solid var(--accent);
            transition: var(--transition);
        }}

        .intent-box p {{
            margin: 0;
            font-size: 1.1rem;
        }}

        .meta-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 30px;
            margin: 30px 0;
            padding: 20px 0;
            border-top: 1px dashed var(--border);
        }}

        code {{
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9rem;
            transition: var(--transition);
        }}

        .activity-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 40px;
        }}

        ul.todo-list {{
            list-style: none;
            padding: 0;
            margin: 0;
            font-size: 0.85rem;
        }}

        ul.todo-list li {{
            margin-bottom: 8px;
            padding-left: 15px;
            position: relative;
        }}

        ul.todo-list li::before {{
            content: "→";
            position: absolute;
            left: 0;
            color: var(--accent);
        }}

        .more {{
            opacity: 0.5;
            font-style: italic;
        }}

        .none {{
            opacity: 0.5;
            font-size: 0.85rem;
            margin: 0;
        }}

        @media (max-width: 900px) {{
            .container {{ grid-template-columns: 1fr; }}
            aside {{ display: none; }}
            .activity-grid {{ grid-template-columns: 1fr; }}
            h1 {{ font-size: 2.2rem; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-meta">COMPILED DIGEST // {parser.date}</div>
        <h1>Project Dashboard</h1>
        <button id="themeToggle" class="theme-toggle">DARK MODE</button>
    </header>

    <div class="container">
        <aside>
            <div class="section-label">PROJECTS</div>
            <ul>
                {sidebar_links}
            </ul>
        </aside>

        <main class="project-list">
            {cards_html}
        </main>
    </div>
    <script>
        const body = document.body;
        const toggle = document.getElementById('themeToggle');
        
        // Initial setup
        if (localStorage.getItem('theme') === 'dark') {{
            body.classList.add('dark-mode');
            toggle.textContent = 'LIGHT MODE';
        }}

        toggle.addEventListener('click', () => {{
            body.classList.toggle('dark-mode');
            const isDark = body.classList.contains('dark-mode');
            toggle.textContent = isDark ? 'LIGHT MODE' : 'DARK MODE';
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        }});
    </script>
</body>
</html>
"""

# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Generate premium HTML dashboard.')
    parser.add_argument('file', type=str, help='Path to markdown daily digest')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser')
    args = parser.parse_args()

    digest_path = Path(args.file)
    if not digest_path.exists():
        print(f"Error: {digest_path} not found.")
        sys.exit(1)

    print(f"Parsing {digest_path}...")
    dp = DigestParser(digest_path)
    
    html_content = generate_html(dp)
    
    output_filename = f"dashboard_{dp.date}.html"
    output_path = Path(output_filename)
    output_path.write_text(html_content, encoding='utf-8')
    
    print(f"Success! Dashboard generated: {output_path.absolute()}")
    
    if not args.no_browser:
        webbrowser.open(f"file://{output_path.absolute()}")

if __name__ == '__main__':
    main()
