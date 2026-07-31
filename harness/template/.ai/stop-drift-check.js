#!/usr/bin/env node
'use strict';

// Stop hook (conditional): after a turn, check whether source files have changed
// more recently than .ai/context.json. If so, remind the model to reconcile the
// context file — but only ONCE per context version, so it never nags turn-to-turn.
//
// Muting works via .ai/.harness-state.json: once we remind for a given context.json
// mtime we stay silent until context.json is updated (which changes its mtime).

const fs = require('fs');
const path = require('path');

const ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const CONTEXT = path.join(ROOT, '.ai', 'context.json');
const STATE = path.join(ROOT, '.ai', '.harness-state.json');

const IGNORE_DIRS = new Set([
  'node_modules', '.git', '.ai', 'dist', 'build', 'out', '.next', '.nuxt',
  'target', 'vendor', 'coverage', '.venv', 'venv', '__pycache__', '.idea',
  '.vscode', 'bin', 'obj', '.turbo', '.cache', '.svelte-kit', '.gradle',
]);

let ctxMtime;
try {
  ctxMtime = fs.statSync(CONTEXT).mtimeMs;
} catch {
  process.exit(0); // no context file — nothing to reconcile
}

// Walk the tree, returning true as soon as any file is newer than context.json.
// Bounded so this stays cheap even on large repos.
let budget = 8000;
function hasNewerSource(dir) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return false;
  }
  for (const entry of entries) {
    if (budget-- <= 0) return false;
    if (entry.isDirectory()) {
      if (IGNORE_DIRS.has(entry.name) || entry.name.startsWith('.')) continue;
      if (hasNewerSource(path.join(dir, entry.name))) return true;
    } else if (entry.isFile()) {
      let m;
      try {
        m = fs.statSync(path.join(dir, entry.name)).mtimeMs;
      } catch {
        continue;
      }
      if (m > ctxMtime) return true;
    }
  }
  return false;
}

if (!hasNewerSource(ROOT)) process.exit(0);

// Drifted — but only remind once per context.json version.
let state = {};
try {
  state = JSON.parse(fs.readFileSync(STATE, 'utf8'));
} catch {
  /* first run */
}
if (state.remindedForMtime === ctxMtime) process.exit(0);

state.remindedForMtime = ctxMtime;
try {
  fs.writeFileSync(STATE, JSON.stringify(state));
} catch {
  /* non-fatal: worst case we remind again next turn */
}

const reminder = [
  'Source files have changed since .ai/context.json was last updated.',
  'Reconcile the context file so the next session stays cheap to orient:',
  '- update task statuses and current_focus',
  '- append any new decisions (with a one-line why) and key_files',
  '- prepend a session_log entry (date, summary, next) and bump project.updated',
].join('\n');

process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'Stop',
      additionalContext: reminder,
    },
  })
);
