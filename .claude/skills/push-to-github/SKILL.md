---
name: push-to-github
description: Push unpushed commits on the current branch to GitHub and open a PR via gh CLI. Aborts if there are no unpushed commits. Ignores working tree state entirely — for uncommitted changes use /commit first.
user_invocable: true
arguments:
  - name: title
    description: Optional PR title override. Defaults to the latest commit subject.
    required: false
  - name: body
    description: Optional PR body override. Defaults to a Summary + Test plan template generated from the unpushed commits.
    required: false
---

# Push to GitHub

Pure "send my committed work upstream" skill. Pushes whatever commits are already in the local branch but not yet on the remote, then opens (or reports) a PR.

**Out of scope** (handled by `/commit`):
- Staging files
- Creating commits
- Creating branches
- Anything about uncommitted changes in the working tree

This skill **does not look at the working tree** at all. Uncommitted files are the user's business; this skill only cares about commits.

---

## Hard rules (MUST)

- MUST NOT run `git add`, `git commit`, `git stash`, or any staging/committing command.
- MUST NOT inspect or report on working-tree cleanliness as a precondition.
- MUST NOT `git push --force`, `git push --no-verify`, `git reset --hard`, `git commit --amend`, `git config`, or `git rebase -i`.
- MUST abort if there are no unpushed commits on the current branch.
- MUST NOT create a PR when on `main` / `master` (those are the trunk — release-please picks up commits from main directly).

---

## Pre-flight (run in parallel)

```bash
git rev-parse --git-dir                    # in a git repo?
git remote get-url origin                  # has remote?
gh auth status                             # gh CLI authed?
git rev-parse --abbrev-ref HEAD            # current branch
```

Bail out if any fail:

| Failure | Action |
|---|---|
| Not a git repo | Exit; tell the user |
| No `origin` remote | Exit; tell user to add one (`gh repo create` / `git remote add origin …`) |
| `gh` not authed | Exit; tell user to run `gh auth login` themselves (do NOT run it — interactive) |
| Detached HEAD (`HEAD` returned) | Exit; tell user to checkout a branch |

---

## Workflow

### Step 1 — Find unpushed commits

```bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Refresh the remote ref so we have an up-to-date view
git fetch origin "$BRANCH" 2>/dev/null || true

# Three cases:
#   (a) upstream is set → diff against @{u}
#   (b) no upstream but remote branch exists → diff against origin/$BRANCH
#   (c) remote branch does not exist → every local commit on this branch is unpushed
if git rev-parse --verify --quiet '@{u}' >/dev/null 2>&1; then
    UNPUSHED=$(git log --oneline '@{u}..HEAD')
    BASE='@{u}'
elif git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    UNPUSHED=$(git log --oneline "origin/${BRANCH}..HEAD")
    BASE="origin/${BRANCH}"
else
    UNPUSHED=$(git log --oneline HEAD)
    BASE='(new branch — no remote counterpart)'
fi
```

### Step 2 — Abort if nothing to push

If `UNPUSHED` is empty, **abort**:

> ❌ Nothing to push. Local branch `<BRANCH>` is up-to-date with `<BASE>`.
>
> If you have uncommitted changes you want to ship, run `/commit` first.

Stop here.

### Step 3 — Show what will be pushed

Print to the user (don't ask for confirmation — pushing committed work is the explicit user request):

```
Pushing <N> commit(s) on <BRANCH> → origin/<BRANCH>:

  abc1234 feat(retrieval): add lexical signals
  def5678 test(retrieval): add lexical signals tests
  …
```

### Step 4 — Push

```bash
git push -u origin "$BRANCH"
```

| Failure | Action |
|---|---|
| Non-fast-forward reject | `git fetch origin "$BRANCH"` → `git pull --rebase origin "$BRANCH"`. Conflicts → abort, ask user. **Never** `--force`. |
| Pre-push hook fails | Show stderr; abort. Do **not** `--no-verify`. |
| Auth fails | Tell user to re-run `gh auth login` or check token scopes |

### Step 5 — PR step (skip when on main / master)

If `BRANCH ∈ {main, master}`:
- skip PR creation entirely
- in the report, mention: "Pushed directly to `<BRANCH>` — release-please will incorporate these commits into the next release PR."
- jump to Step 6

Otherwise, check whether a PR already exists for this branch:

```bash
gh pr view --json url,state,title 2>/dev/null
```

- If `state == OPEN` → skip create; record the existing URL
- If `state == MERGED` / `CLOSED` → create a fresh PR (branch was re-used)
- If `gh pr view` fails (no PR yet) → create

Create:

```bash
# Title: ${title} arg if provided, else latest commit subject
TITLE=$(git log -1 --pretty=format:'%s')   # or ${title}

# Body: ${body} arg if provided, else generated from unpushed commit subjects
BODY=$(cat <<EOF
## Summary

$(git log --pretty=format:'- %s' "${BASE}..HEAD")

## Test plan
- [ ] <fill in relevant checks>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)

gh pr create --title "$TITLE" --body "$BODY"
```

Note: PR title is *not* validated against conventional-commits in this skill. Release-please configuration concerns the commit subjects themselves (which the user authored via `/commit` or by hand). If the title isn't conventional, the worst case is release-please ignores this PR — not a hard failure.

### Step 6 — Report back

Output:
- Branch: `<BRANCH>`
- Pushed range: `<BASE>..<HEAD short SHA>` (or "new branch, all commits")
- Commits pushed: `<N>`
- PR URL (if a feature branch) — newly created or pre-existing
- For main / master pushes: note that release-please will accumulate these in its release PR

---

## Quick decision tree

```
unpushed commits exist? ── no → ABORT: "nothing to push"
   │
   yes
   ▼
git push -u origin <branch>     (no --force, no --no-verify)
   │
   ▼
branch == main/master? ── yes → done; note release-please will see these commits
   │
   no
   ▼
gh pr view → state == OPEN? ── yes → report existing URL
                              no  → gh pr create
   │
   ▼
report branch / range / PR URL
```

---

## What this skill explicitly does NOT do

- Does not read `git status` or `git diff` for working-tree changes
- Does not stage, commit, amend, or stash
- Does not create or switch branches
- Does not validate commit messages (that's `/commit`'s job)
- Does not force-push or bypass hooks

If any of those are needed, use `/commit` first or do it manually before invoking this skill.
