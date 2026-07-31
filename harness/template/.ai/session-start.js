#!/usr/bin/env node
'use strict';

// SessionStart hook: inject the persisted context file directly into the model's
// context, so a new (or post-compaction) session orients itself without spending
// a tool call to read the file. Silent when there is no context file yet.

const fs = require('fs');
const path = require('path');

const ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const CONTEXT = path.join(ROOT, '.ai', 'context.json');

let raw;
try {
  raw = fs.readFileSync(CONTEXT, 'utf8').trim();
} catch {
  process.exit(0); // no context file — stay quiet on a fresh project
}
if (!raw) process.exit(0);

const additionalContext = [
  'Persisted project context from .ai/context.json — this is your working memory.',
  'Orient from it before exploring the codebase; keep it current as you work.',
  '',
  raw,
].join('\n');

process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext,
    },
  })
);
