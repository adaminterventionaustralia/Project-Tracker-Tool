# AI Harness — Context Protocol

This project uses a persistent context file so that each new AI session can
orient itself in **a few hundred tokens instead of re-reading the whole
codebase**. That file is the single source of truth for "where are we".

**State file:** [.ai/context.json](.ai/context.json)
**Shape:** [.ai/context.schema.json](.ai/context.schema.json)

> Two hooks (in [.claude/settings.json](.claude/settings.json)) back this up: a
> **SessionStart** hook injects `context.json` into context automatically (so
> orientation costs zero tool calls), and a **Stop** hook reminds you to
> reconcile the file when source has changed since it was last updated. The hooks
> are a safety net — the protocol below is still your responsibility.

---

## 1. Session start — orient from the JSON, not the code

The SessionStart hook has already injected `.ai/context.json` into your context
— **don't spend a tool call re-reading it** unless the injected copy is missing
(hook failure, fresh project) or you've edited the file during this session.
Treat it as your working memory:

- `project.goal` / `project.stack` — what this is and what it's built with.
- `current_focus` — the one thing we're working on right now. Start here.
- `tasks` — the live to-do list with statuses.
- `decisions` — choices already made (and why). **Do not re-litigate these.**
- `key_files` — the map of where things live, so you don't have to search.
- `open_questions` — known unknowns waiting on the user or on investigation.
- `glossary` — project-specific terms, so you don't misread domain language.
- `session_log` — recent history; the newest entry's `next` is your starting point.

Only explore the codebase directly when the JSON is missing, stale, or
insufficient for the task at hand. If you discover the JSON is wrong, fix it.

## 2. During work — keep the JSON current as you go

Update `.ai/context.json` as facts change — not just at the end:

- Moved a task forward? Update its `status` (`todo` → `doing` → `done`, or `blocked`).
- Made a non-obvious choice? Append to `decisions` with a one-line `why`.
- Learned where something important lives? Add it to `key_files`.
- Hit a question only the user can answer? Add it to `open_questions`.
- Got an answer to an `open_question`? **Delete it** — and if the answer is
  durable, record it as a decision.
- Ran into a project-specific term worth remembering? Define it in `glossary`.

Keep entries **terse and high-signal** — this file is read every session, so
every token has recurring cost. Prune what's no longer true; delete completed
tasks that no longer carry context. This is a live working set, not a changelog.

## 3. Checkpointing — before the session ends

You can't reliably predict when a session will end, so **checkpoint after
completing any significant chunk of work** (the Stop hook's drift reminder is
the backstop, not the trigger):

1. Set `current_focus` to what should be tackled next.
2. Update `session_log` (newest first): one entry per session with `date`, a
   one-line `summary` of what changed, and `next` (the concrete next step).
   **If this session already has an entry, amend it** — don't stack a new entry
   per checkpoint.
3. Update `project.updated` to today's date (ISO `YYYY-MM-DD`).
4. Make sure `tasks` statuses reflect reality.

## Rules

- **The JSON is the source of truth for orientation.** Prefer it over re-deriving
  facts from the code.
- **Small and current beats complete.** A lean, accurate file is worth more than
  an exhaustive stale one.
- **Stay within the schema.** It is closed (`additionalProperties: false`) —
  don't invent new fields; if a new field is genuinely needed, extend
  `context.schema.json` in the same change.
- Keep the `session_log` to roughly the **last 5–8 entries**; summarize or drop
  older ones.
- Timestamps are ISO dates (`YYYY-MM-DD`) — use the actual current date from
  your environment, never a guessed one.
- Don't record secrets, tokens, or credentials here.

<!--
Everything below this line is normal CLAUDE.md territory — add project-specific
build/test/style conventions here as the project grows.
-->
