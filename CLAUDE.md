@AGENTS.md

## Fork Workflow (try-ama/marimo)

This is a fork of marimo-team/marimo. See [FORK.md](FORK.md) for full documentation.

### Remotes

```
origin   -> try-ama/marimo (our fork)
upstream -> marimo-team/marimo (original)
```

### Branch Strategy

- **`main`**: Mirror of upstream. NEVER commit directly.
- **Feature branches**: All custom work goes here (e.g., `ama-integrations`)

### Starting a New Feature

```bash
# 1. Ensure main is synced with upstream
uvx hatch run fork-sync-main

# 2. Create feature branch from main
git checkout main
git checkout -b my-feature-name

# 3. Make changes, commit normally
git add <files>
git commit -m "feat: description"

# 4. Push to origin
git push -u origin my-feature-name
```

### Shipping Changes to Fork

```bash
# Push your feature branch
git push origin my-feature-name

# Or after rebasing (use --force-with-lease for safety)
uvx hatch run fork-push-branch
```

### Keeping Feature Branch Updated

```bash
# 1. Sync main with upstream
uvx hatch run fork-full-sync

# 2. Rebase your branch onto updated main
uvx hatch run fork-rebase-branch

# 3. Push rebased branch (force-with-lease)
uvx hatch run fork-push-branch
```

### Fork Maintenance Scripts

| Command | Description |
|---------|-------------|
| `uvx hatch run fork-status` | Check commits behind/ahead of upstream |
| `uvx hatch run fork-sync-main` | Sync main with upstream (fast-forward only) |
| `uvx hatch run fork-push-main` | Push synced main to origin |
| `uvx hatch run fork-rebase-branch` | Rebase current branch onto main |
| `uvx hatch run fork-push-branch` | Push branch with --force-with-lease |
| `uvx hatch run fork-full-sync` | Fetch + sync main in one command |
| `uvx hatch run fork-upstream-log` | Show recent upstream commits |

### Safety Rules

1. **Never commit to main** - It mirrors upstream
2. **Never use `--force`** - Always use `--force-with-lease` (scripts do this)
3. **Sync before branching** - Run `fork-sync-main` before starting new work
4. **Document customizations** - Update FORK.md when adding features

### If Something Goes Wrong

```bash
# Check current state
uvx hatch run fork-status
git status
git log --oneline -10

# If main diverged from upstream (fork-sync-main failed)
git checkout main
git reset --hard upstream/main  # WARNING: discards local main commits
git push origin main --force-with-lease

# If rebase has conflicts
# Resolve conflicts, then:
git add <resolved-files>
git rebase --continue
# Or abort:
git rebase --abort
```
