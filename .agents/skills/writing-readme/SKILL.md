---
name: writing-readme
description: Use when creating or updating the root README.md for any project, especially AI/ML projects with agents, pipelines, or multi-source documentation that may contain outdated or duplicate content
---

# Writing README

## Overview

Write or incrementally update a project's root `README.md` by cross-referencing
actual code, configuration, and documentation — never by trusting docs at face
value. The skill enforces a 3-phase workflow: gather evidence from code and
docs, critically review for outdated/duplicate/conflicting content, then write
only what is verified.

**Core principle:** Every claim in the README must be backed by evidence from
the current codebase. If docs and code disagree, code wins.

## When to Use

- User asks to create, write, or generate a README
- User asks to update, refresh, or fix the README
- README is missing and user wants one
- User mentions README is outdated

## When NOT to Use

- Updating `docs/README.md` or subdirectory READMEs (this skill is root
  `README.md` only)
- Writing technical reports → use `writing-insurevn-technical-reports`
- Writing changelogs → use `changelog-generator`

## Output

- **File**: `README.md` at project root only
- **Language**: English
- **Mode**: Full generation (no README exists) or incremental update (README
  exists)

---

## Phase 1: Evidence Gathering

Scan the project systematically. Do NOT skip any source.

### 1.1 Project Structure

```bash
# Directory tree (depth 2-3)
tree -L 3 -I '__pycache__|node_modules|.git|*.pyc|.venv|venv' .

# Key config files
cat pyproject.toml 2>/dev/null || cat setup.py 2>/dev/null || cat package.json 2>/dev/null
cat requirements.txt 2>/dev/null
```

### 1.2 Source Code

Read entry points and core modules to understand what the project actually does:

- Main entry point (`main.py`, `app.py`, `index.ts`, etc.)
- Config/settings module
- Core business logic directories
- Agent definitions (if AI project)
- Service layer
- API routes

**Do NOT read every file.** Read enough to verify architecture claims.

### 1.3 Documentation Files

```bash
# Find all markdown docs
find docs/ -name "*.md" -type f 2>/dev/null | sort

# Read project instruction files
cat AGENTS.md GEMINI.md CLAUDE.md 2>/dev/null
```

Read **every** markdown file in `docs/`. Pay attention to:

- Architecture docs
- Work logs
- Specs and plans
- Database docs

### 1.4 Work Log Files

```bash
ls -la docs/work_log/ 2>/dev/null
```

Read each work log file. For each file, extract:

- What was done
- Key outcomes
- Date

These become summaries in the Work Log section.

### 1.5 Git History

```bash
# Recent activity
git log --oneline -20
# Current branch and status
git branch --show-current
git status --short
```

### 1.6 Existing README

```bash
cat README.md 2>/dev/null
```

If README exists → **incremental update mode**. If not → **full generation
mode**.

---

## Phase 2: Critical Review

**This phase is MANDATORY. Do NOT skip to writing.**

Before writing a single line of README, analyze all gathered evidence
internally. Do not output this analysis as a separate artifact — process it
internally, then write the README.

### 2.1 Cross-Reference Docs vs Code

For every major claim found in docs, verify against actual code:

| Check | How |
|---|---|
| Feature X exists? | Find implementation in source code |
| Tech Y is used? | Check imports, requirements, config |
| Architecture pattern Z? | Verify in code structure and agent definitions |
| Agent A does B? | Read agent source code |
| Data flows through C? | Trace in code |

**If docs say X but code says Y → use Y.** Note the discrepancy internally.

### 2.2 Detect Duplicates Across Docs

Multiple docs often describe the same thing differently. For each topic:

1. List all docs that mention it
2. Compare versions — which is newest?
3. Compare accuracy — which matches current code?
4. Choose the **most accurate + most recent** source
5. If they conflict, trust code over all docs

### 2.3 Identify Outdated Content

For every piece of information, determine:

- **What is outdated?** (specific claim)
- **What replaces it?** (current state from code)
- **Why is it outdated?** (what changed — commit, refactor, new feature)

Common staleness patterns:

- Tech listed but not in `requirements.txt` / `package.json`
- Agent described but not implemented in code
- Architecture diagram references removed components
- Feature listed as "done" but code shows partial implementation
- Config keys documented but not in `.env.example` or config module

### 2.4 Resolve Information Hierarchy

When sources conflict, trust in this order:

1. **Running code** (highest trust)
2. **Config files** (`pyproject.toml`, `requirements.txt`, `.env.example`)
3. **Project instruction files** (`AGENTS.md`, `GEMINI.md`)
4. **Architecture docs** (with date — newer wins)
5. **Work logs** (factual records)
6. **Historical docs** (lowest trust)

---

## Phase 3: Writing

### Mode A: Full Generation (no README exists)

Generate all mandatory sections from the template below, populated exclusively
with verified facts from Phase 2.

### Mode B: Incremental Update (README exists)

Rules for incremental updates:

1. **Read the existing README completely first**
2. **Preserve existing structure** — do not reorganize sections
3. **Preserve existing prose** that is still accurate
4. **Only modify what has evidence of being wrong or missing**
5. **Add new sections** at the correct position per template order
6. **Do NOT rewrite sections** that are accurate but "could be better styled"
7. **Do NOT remove content** unless it is factually wrong (confirmed in Phase 2)

For each change, you must internally justify:

- What exactly is being changed?
- What evidence proves the old content is wrong/missing?
- What is the verified replacement?

**Anti-patterns — NEVER do these:**

- ❌ Rewrite the entire README when only 1 section needs updating
- ❌ Change heading structure that is working fine
- ❌ Remove content without confirming it is outdated
- ❌ Add "nice-to-have" sections the user did not ask for
- ❌ Change formatting/style of existing sections
- ❌ Duplicate information already in other sections

---

## Mandatory Sections Template

Every README must contain these sections in this order. If a section has no
verified content, write a minimal placeholder with a `<!-- TODO -->` comment.

```markdown
# Project Name

> One-line description of the project

![Architecture Overview](path/to/diagram)

## Overview

2-4 paragraphs: what the project is, what problem it solves, who it is for.
Must be grounded in actual implemented functionality, not aspirational goals.

## Key Features

Bullet list of features that **currently work** in the codebase.
Do NOT list planned features here. Use present tense.

- **Feature Name**: One-sentence description
- **Feature Name**: One-sentence description

## Architecture

High-level system design. Include or link architecture diagram if available.
Keep concise — link to `docs/architecture/` for full details.

Describe only what is actually implemented, not theoretical designs.

## Tech Stack

Table format, grouped by layer:

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Runtime | FastAPI, Uvicorn |
| ... | ... |

Verify every entry exists in requirements/package files.

## Project Structure

Abbreviated tree — top-level directories + key files with 1-line descriptions.
Do NOT list every file. Max 30 lines.

## Quick Start

Step-by-step instructions that a new developer can copy-paste:

1. Clone
2. Install dependencies
3. Configure (env vars)
4. Run

Max 5-7 steps. Every command must be tested/verified.

## [Conditional Sections]

Include ONLY if the project has these. Detect from code:

- **Agent System** — if project uses AI agents with defined roles
- **Knowledge Graph** — if project has graph DB integration
- **API Reference** — if project exposes API endpoints
- **Model Training** — if project has training/fine-tuning code

Each conditional section should be concise and link to detailed docs.

## Work Log

Summarize each file in `docs/work_log/` (or equivalent). One entry per file:

- **[Report Title](docs/work_log/filename.md)** — 1-2 sentence summary of
  what was done and key outcomes.

Order by date, most recent first. Read each file to write accurate summaries.

## Testing

How to run tests, test structure, and any test-related conventions.

```bash
# Example test commands
pytest tests/
```

## Documentation

Links to detailed documentation organized by topic:

- [Architecture Docs](docs/architecture/)
- [Database Specs](docs/database/)
- etc.

## Roadmap

Checklist format showing project status:

- [x] Completed item
- [x] Another completed item
- [ ] In progress or planned item
- [ ] Future planned item

Derive from actual project state — completed items from code, planned items
from specs/plans/issues.

## Contributing

Contribution guidelines. If none defined, write minimal:
fork → branch → PR workflow.

## License

State the license. If no LICENSE file exists, write
`<!-- TODO: Add LICENSE file -->`.
```

---

## Conditional Section Detection

Scan the codebase for these signals to decide which conditional sections to
include:

| Section | Detection signals |
|---|---|
| Agent System | `agents/` directory, LangChain/LangGraph agent definitions |
| Knowledge Graph | Neo4j imports, graph schema files, `knowledge_graph/` dir |
| API Reference | FastAPI/Express routes, OpenAPI specs |
| Model Training | Training scripts, fine-tuning configs, model weights dirs |

Only include a conditional section if you find **implementation code**, not just
documentation about it.

---

## Work Log Summarization Rules

When summarizing work log files:

1. **Read the full file** — do not guess from the filename
2. **Extract the core outcome** — what was built/fixed/analyzed
3. **Keep to 1-2 sentences** — this is a summary, not a reproduction
4. **Link to the file** — reader can click through for details
5. **Use consistent format** across all entries
6. **Order by date** — most recent first

---

## Verification

After writing/updating the README, verify:

```bash
# Check for placeholder text
rg -n "TODO|TBD|FIXME|placeholder|fill.in|REPLACE" README.md || true

# Verify all internal links resolve
rg -oP '\[.*?\]\(((?!http)[^)]+)\)' README.md | while read -r link; do
  path=$(echo "$link" | grep -oP '\(([^)]+)\)' | tr -d '()')
  [ ! -e "$path" ] && echo "BROKEN: $path"
done || true

# Verify README is not bloated
wc -l README.md
# Target: 150-400 lines for most projects
```

Fix any broken links or leftover placeholders before finishing.
