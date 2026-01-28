# Marimo Fork Customizations

This is a fork of [marimo-team/marimo](https://github.com/marimo-team/marimo) maintained by try-ama.

## Fork Strategy

We maintain a long-running fork that:
- Keeps `main` as a mirror of upstream (never commit directly)
- Uses feature branches (e.g., `ama-integrations`) for custom features
- Rebases feature branches onto `main` periodically

## Remotes

```
origin   -> git@github.com:try-ama/marimo.git (our fork)
upstream -> git@github.com:marimo-team/marimo.git (original)
```

## Fork Maintenance Scripts

All scripts are defined in `pyproject.toml` and run via hatch:

```bash
# Check how far behind/ahead of upstream
uvx hatch run fork-status

# Fetch latest from both remotes
uvx hatch run fork-fetch

# Sync main with upstream (fast-forward only, safe)
uvx hatch run fork-sync-main

# Push main to origin
uvx hatch run fork-push-main

# Rebase current feature branch onto main
uvx hatch run fork-rebase-branch

# Push feature branch with --force-with-lease (safe)
uvx hatch run fork-push-branch

# Full sync: fetch + sync main (then manually rebase branch)
uvx hatch run fork-full-sync

# Show recent upstream commits not yet in main
uvx hatch run fork-upstream-log
```

## Sync Workflow

### Weekly Sync (or before releases)

```bash
# 1. Check current status
uvx hatch run fork-status

# 2. Sync main with upstream
uvx hatch run fork-sync-main
uvx hatch run fork-push-main

# 3. If on a feature branch, rebase it
uvx hatch run fork-rebase-branch
uvx hatch run fork-push-branch
```

### Handling Conflicts During Rebase

If conflicts occur during `fork-rebase-branch`:

1. Resolve conflicts manually
2. `git add <resolved-files>`
3. `git rebase --continue`
4. Run `uvx hatch run fork-push-branch` when complete

## Custom Features

<!-- Document your customizations here -->

### 1. [Feature Name] (files modified)
- Description of what was changed
- Why it was necessary
- Files modified: `path/to/file.py`

## Installation in Other Projects

### From Branch (Development)
```toml
[project]
dependencies = [
    "marimo @ git+https://github.com/try-ama/marimo.git@ama-integrations",
]
```

### From Commit (Production)
```toml
[project]
dependencies = [
    "marimo @ git+https://github.com/try-ama/marimo.git@COMMIT_HASH",
]
```

Or with uv:
```bash
uv add "marimo @ git+https://github.com/try-ama/marimo.git@ama-integrations"
```

## Upstream Contribution Policy

If a feature is general-purpose and could benefit the marimo community:
1. Create the feature in a separate branch
2. Submit a PR to upstream
3. Once merged upstream, remove from our fork during next sync
