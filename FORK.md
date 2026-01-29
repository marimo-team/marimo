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

## Building Frontend Assets

This fork includes a GitHub Actions workflow that builds the frontend assets and creates installable Python wheels. This solves the issue of missing JS/CSS assets when installing directly from git.

### Automatic Builds

The `build-release.yml` workflow runs automatically on:
- Push to `main` branch
- Push to feature branches (`ama-*`, `feat/*`, `feature/*`)
- Pull requests to `main`
- Manual trigger via GitHub Actions UI

Each build produces:
- Python wheel (`*.whl`) with bundled frontend assets
- Source distribution (`*.tar.gz`)

### Getting Built Artifacts

#### From GitHub Actions
1. Go to **Actions** tab in the repository
2. Select a successful **Build & Release** workflow run
3. Download the wheel artifact from the **Artifacts** section

#### Creating a Release
1. Go to **Actions** → **Build & Release**
2. Click **Run workflow**
3. Check "Create a GitHub release"
4. Click **Run workflow**

This creates a tagged release with downloadable wheel files.

### Local Build

To build the frontend locally:

```bash
# Ensure prerequisites are installed
make check-prereqs

# Build frontend assets
make fe

# Build Python wheel
uv build --wheel

# The wheel is in dist/
ls dist/*.whl
```

## Installation in Other Projects

### From GitHub Release (Recommended)

Install a pre-built wheel directly from a GitHub release:

```bash
# Install specific release
pip install "marimo @ https://github.com/try-ama/marimo/releases/download/fork-VERSION/marimo-VERSION-py3-none-any.whl"

# Or with uv
uv add "marimo @ https://github.com/try-ama/marimo/releases/download/fork-VERSION/marimo-VERSION-py3-none-any.whl"
```

### From Downloaded Wheel

If you've downloaded a wheel from GitHub Actions artifacts or releases:

```bash
pip install ./marimo-*.whl
# or
uv pip install ./marimo-*.whl
```

### From Branch (Development - No Frontend Assets)

**Note:** Installing directly from git does NOT include built frontend assets. The application will fall back to CDN assets, which may not include your fork's customizations.

```toml
[project]
dependencies = [
    "marimo @ git+https://github.com/try-ama/marimo.git@ama-integrations",
]
```

### From Commit (Production - No Frontend Assets)
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
