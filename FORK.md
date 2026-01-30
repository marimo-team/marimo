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

## Build & Release Process

The fork uses GitHub Actions to automatically build frontend assets and Python wheels.

### Automatic Builds

Every push to these branches triggers a build:
- `main` - Auto-creates a GitHub release
- `ama-*` - Builds only, no release
- `feat/*`, `feature/*` - Builds only, no release

### Version Format

Versions follow the pattern `{upstream}-fork.{iteration}`:
- `0.19.6-fork.1` - First fork release based on upstream 0.19.6
- `0.19.6-fork.2` - Second iteration (e.g., fork-specific fixes)
- `0.19.7-fork.1` - After syncing with upstream 0.19.7

The iteration number is tracked in `.fork-version`.

### Creating a Release

**Automatic (recommended):** Push to `main` branch → release created automatically.

**Manual (for feature branches):**
1. Go to Actions → "Build & Release"
2. Click "Run workflow"
3. Check "Create a GitHub release"
4. Optionally override the fork iteration number

### Bumping the Fork Version

When making changes that warrant a new release:

```bash
# Increment the iteration number
echo "2" > .fork-version
git add .fork-version
git commit -m "chore: bump fork version to 2"
```

### Using Fork Releases

**Install via pip:**
```bash
pip install "marimo @ https://github.com/try-ama/marimo/releases/download/v0.19.6-fork.1/marimo-0.19.6-py3-none-any.whl"
```

**Use CDN assets (for containers/deployments):**
```bash
marimo edit --asset-url "https://cdn.jsdelivr.net/gh/try-ama/marimo@v0.19.6-fork.1/_static"
```

### CDN Asset URL Pattern

Assets are served via jsDelivr from GitHub releases:
```
https://cdn.jsdelivr.net/gh/try-ama/marimo@v{version}/_static
```

This is useful for:
- Docker containers that bundle only Python (no frontend build)
- Deployments where you want to serve assets from CDN
- Reducing container image size

### Version Reconciliation After Upstream Sync

When syncing with a new upstream version:

1. Sync main with upstream: `uvx hatch run fork-full-sync`
2. Reset iteration to 1: `echo "1" > .fork-version`
3. Rebase feature branch: `uvx hatch run fork-rebase-branch`
4. Push to trigger new release

## Upstream Contribution Policy

If a feature is general-purpose and could benefit the marimo community:
1. Create the feature in a separate branch
2. Submit a PR to upstream
3. Once merged upstream, remove from our fork during next sync
