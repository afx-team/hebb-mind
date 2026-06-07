---
name: commit
description: Stage and commit current changes with an auto-generated conventional-commits message. From main, first creates a feature branch. Does NOT push.
user_invocable: true
arguments:
  - name: message
    description: Optional full commit message override. If omitted, generated from diff in conventional-commits format. Must start with a valid type.
    required: false
  - name: type
    description: Optional commit type hint (feat, fix, refactor, docs, chore, perf, test, build, ci, style). Overrides auto-detection.
    required: false
  - name: scope
    description: Optional scope override (e.g. server, retrieval, eval). Overrides auto-detection from paths.
    required: false
  - name: paths
    description: Optional space-separated list of paths to include. If omitted, includes everything from `git status` after sensitive-file check.
    required: false
---

# Commit Current Changes

Stage and commit pending changes with a conventional-commits message. **Does not push.** For push + PR, use `/push-to-github` after.

This repo follows **conventional-commits** for a consistent history that maps cleanly onto the manually-maintained `CHANGELOG.md` sections (Added / Fixed / Performance / Changed / Documentation). Releases are manual — versioning and the changelog are bumped by hand on release (the release-please automation was removed).

---

## Hard rules (MUST)

- MUST use conventional-commits format. Type is one of: `feat`, `fix`, `refactor`, `perf`, `docs`, `chore`, `test`, `build`, `ci`, `style`, `revert`.
- MUST NOT `git commit --amend`, `git reset`, `git push`, `git config`, `git rebase -i`, `git commit --no-verify`.
- MUST NOT commit files matching: `.env*`, `*.key`, `*.pem`, `id_rsa*`, `credentials*`, `secrets*`, `*.db` (incl. `hebb.db`), `.claude/scheduled_tasks.lock`, any file with `secret` / `password` / `token` in the name. If `git status` shows any, **abort** and ask the user.
- MUST stage explicitly by path (`git add <paths>`) — never bare `git add .` / `git add -A`. List what will be staged first.
- MUST create a new feature branch when current branch is `main` (or `master`). MUST NOT commit directly to main.
- MUST show the generated commit message to the user and get confirmation before running `git commit`.
- MUST follow the project's `CLAUDE.md` — but this skill only ships code that's already in the working tree; it does not author new code.

---

## Pre-flight (run in parallel)

```bash
git rev-parse --git-dir                    # in a git repo?
git rev-parse --abbrev-ref HEAD            # current branch
git status --porcelain                     # working tree state
git log -5 --pretty=format:'%s'            # recent commit style reference
```

If not a git repo → exit.

---

## Workflow

### Step 1 — Classify state

From `git status --porcelain`:

- If output is empty → nothing to commit. Print "working tree clean" and exit.
- Otherwise → continue to Step 2.

### Step 2 — Sensitive-file gate

Scan the porcelain output for these patterns:

```
.env  .env.*  *.key  *.pem  id_rsa*  credentials*  secrets*  *.db  hebb.db
*secret*  *password*  *token*  .claude/scheduled_tasks.lock
```

If **any** match, **abort**:

> ⚠️ Detected potentially-sensitive paths:
> `<list>`
> Aborting to avoid leaking secrets. Tell me which paths to include (e.g. `paths="file1 file2"`) or add them to `.gitignore` first.

### Step 3 — Inspect changes

```bash
git diff --staged                          # already-staged changes
git diff                                   # unstaged tracked changes
git status --porcelain                     # for path classification
```

Cap each diff output by paths if it's huge — read just enough to classify type/scope.

### Step 4 — Generate commit message

Priority: `${message}` argument > auto-generated.

If `${message}` is provided:
- validate it matches the conventional-commits regex (see Step 5 of `/push-to-github`)
- use it verbatim
- skip the generation logic, jump to Step 5

If auto-generating:

**Type** (priority: `${type}` argument > auto-detect):
- `feat` — new functionality, new public API, new CLI command, new endpoint, new module
- `fix` — bug fix, corrected behavior, error handling fix
- `refactor` — code change with no behavior change (rename, extract, restructure)
- `perf` — performance improvement
- `docs` — only changes under `repo_pages/`, `README*`, `*.md`, or docstrings
- `test` — only changes under `tests/` or `eval/`
- `chore` — deps, lockfiles, `.gitignore`, build config, tooling, `.claude/**`
- `build` — only `pyproject.toml` build section, Dockerfile, packaging
- `ci` — only `.github/workflows/**`, `.github/dependabot.yml`
- `style` — formatting only (whitespace, quotes), no logic change

When multiple types apply, pick the most user-visible one (`feat` > `fix` > `refactor` > `perf` > `docs` > `test` > `chore`).

**Scope** (priority: `${scope}` argument > auto-detect):

| Most-changed path | Scope |
|---|---|
| `src/hebb/server/**` | `server` |
| `src/hebb/cli/**` | `cli` |
| `src/hebb/retrieval/**` | `retrieval` |
| `src/hebb/storage/**` | `storage` |
| `src/hebb/integrations/claude_code/**` | `claude-code` |
| `src/hebb/embedding/**` | `embedding` |
| `src/hebb/graph/**` | `graph` |
| `eval/**` | `eval` |
| `tests/**` | `tests` |
| `.github/**` | `ci` |
| `repo_pages/**` | `docs` |
| `.claude/**` | `claude` |
| mixed / unclear | omit scope |

**Subject** (after `<type>(<scope>):` or `<type>:`):
- Imperative mood ("add foo", not "added foo" / "adds foo")
- Lowercase first letter, no trailing period
- ≤72 chars total line length
- Describe *what* changed at a high level; specifics go in body

**Body** (only if non-obvious): one short paragraph on *why*. Skip for self-evident changes.

**Breaking change**: if the diff removes/renames a public function, CLI flag, `__all__` export, or HTTP endpoint, append `!` after the scope (`feat(cli)!: rename X to Y`) AND add a `BREAKING CHANGE:` footer describing the migration.

**Multiple unrelated changes**: if the working tree has 2+ unrelated concerns (e.g. a feature + a docs fix), **ask the user** whether to:
- (a) make multiple commits — recommended
- (b) bundle them all (use most-prominent type + body listing all changes)

### Step 5 — Confirm message with user

Show the user:

```
About to commit:

  Branch: <current-or-new-branch>
  Files (N):
    M  src/hebb/foo.py
    A  src/hebb/bar.py
    ...

  Message:
    feat(scope): subject line

    Optional body paragraph explaining why.

OK to proceed? [respond yes / edit / cancel]
```

If user says edit → take their revised message verbatim.
If user says cancel → stop, don't commit.
If user says yes → continue.

### Step 6 — Create branch if on main

```bash
CURRENT=$(git rev-parse --abbrev-ref HEAD)
```

- If `CURRENT` ∉ {`main`, `master`} → reuse it. Skip branch creation.
- Else → derive `SLUG` from the commit message:
  - take the part after `<type>(<scope>):` (the subject)
  - lowercase, replace runs of non-alphanumeric with `-`, trim leading/trailing `-`
  - prefix with `<type>/` (e.g. `feat/add-health-endpoint`, `fix/fts5-stemming`)
  - truncate to 50 chars total
  - if `git rev-parse --verify "refs/heads/$SLUG"` succeeds (branch exists locally) OR `git ls-remote --exit-code --heads origin "$SLUG"` succeeds (exists on remote), append `-2`, `-3`, … until unique
  - `git switch -c "$SLUG"`

### Step 7 — Stage explicit paths

Determine the path list:
- if `${paths}` provided → use those exact paths
- else → take all paths from `git status --porcelain` (excluding the sensitive ones already rejected in Step 2)

Print exactly what will be staged:

```
Staging:
  M  eval/benchmarks/convomem_bench.py
  M  src/hebb/retrieval/searcher.py
  A  src/hebb/retrieval/lexical_signals.py
  ...
```

Then:

```bash
git add <path1> <path2> ...
```

Re-check no sensitive files snuck in:

```bash
git diff --cached --name-only | grep -E '\.(env|key|pem|db)$|credentials|secrets|password|token|id_rsa' && echo "ABORT"
```

### Step 8 — Commit

Use HEREDOC for safe quoting:

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<optional body>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If a pre-commit hook fails:
1. Read the stderr
2. Decide if the hook is right (e.g. ruff caught a lint issue → fix it; mypy caught a type error → fix it)
3. Fix the underlying issue with `Edit`
4. Re-stage the affected files: `git add <paths>`
5. Create a **new** commit (do NOT `--amend`)

If the hook reports a non-fixable issue (e.g. a hook config error), abort and tell the user.

### Step 9 — Report back

Output:
- Branch name (created or reused)
- Commit SHA: `git rev-parse --short HEAD`
- Commit subject (first line of message)
- Next step hint: "Run `/push-to-github` to push and open a PR."

---

## Quick decision tree

```
working tree clean? ── yes → "nothing to commit", done
   │
   no
   ▼
sensitive files in changes? ── yes → ABORT, ask user
   │
   no
   ▼
generate conventional-commits message ── show to user, get confirmation
   │
   ▼
on main? ── yes → git switch -c <slug-from-message>
   │
   no → reuse current branch
   ▼
git add <explicit paths>     (re-check no secrets in staged)
   │
   ▼
git commit (HEREDOC; no --amend, no --no-verify)
   │
   pre-commit hook fails? ── yes → fix root cause, re-stage, NEW commit
   │
   no
   ▼
report branch / SHA / subject; hint /push-to-github
```

---

## Failure handling summary

| Failure | Action |
|---|---|
| Pre-commit hook fails | Show stderr; fix root cause; re-stage; new commit (no `--amend`) |
| Sensitive file detected | Abort; ask user which paths to include |
| Branch slug collision | Append `-2`, `-3`, … |
| User cancels at confirmation | Stop cleanly; don't stage or commit |
| Multiple unrelated changes | Ask user: split into multiple commits, or bundle |
| Provided `${message}` invalid | Show the regex; ask user to fix |
| Detached HEAD | Abort; tell user to checkout a branch first |
