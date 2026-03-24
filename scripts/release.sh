#!/bin/bash
set -e

# Colors and formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

print_step() {
  echo -e "\n${BOLD}${GREEN}=== $1 ===${NC}\n"
}

print_warning() {
  echo -e "${YELLOW}WARNING: $1${NC}"
}

print_error() {
  echo -e "${RED}ERROR: $1${NC}"
}

confirm() {
  echo -e -n "${BOLD}$1 (y/N) ${NC}"
  read -r response
  [[ "$response" == "y" ]]
}

# Header
echo -e "${BOLD}${GREEN}"
echo "╔════════════════════════════════════╗"
echo "║        marimo release script       ║"
echo "╚════════════════════════════════════╝"
echo -e "${NC}"

# Check if version type is provided
if [ -z "$1" ]; then
  echo -e "\nAvailable version types:"
  # echo "  - major (x.0.0)"
  echo "  - minor (0.x.0)"
  echo "  - patch (0.0.x)"
  print_error "Please specify version type: ./release.sh <minor|patch>"
  exit 1
fi

VERSION_TYPE=$1

# Validate version type
if [[ ! "$VERSION_TYPE" =~ ^(minor|patch)$ ]]; then
  print_error "Invalid version type. Use: minor or patch"
  exit 1
fi

# Check gh CLI is available
if ! command -v gh &> /dev/null; then
  print_error "gh CLI is required but not installed. See https://cli.github.com/"
  exit 1
fi

# Check if on main branch
print_step "Checking git branch"
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
  print_error "Not on main branch. Current branch: $BRANCH"
  echo "Please run: git checkout main"
  exit 1
fi

# Check git state
print_step "Checking git status"
if [ -n "$(git status --porcelain)" ]; then
  print_error "Git working directory is not clean"
  echo "Please commit or stash your changes first:"
  git status
  exit 1
fi

# Pull latest changes
print_step "Pulling latest changes"
git pull origin main

# Run uv version
print_step "Updating version"
echo -e "Running: uv version --bump $VERSION_TYPE\n"
uv version --bump $VERSION_TYPE
NEW_VERSION=$(NO_COLOR=1 uv version --short) # re-run to get the version

# Summary and confirmation
echo -e "\n${BOLD}Release Summary:${NC}"
echo "  • New Version: $NEW_VERSION"
echo "  • A PR will be created: release/$NEW_VERSION -> main"
echo "  • After merge, a tag will be created automatically"

if ! confirm "Proceed with release?"; then
  print_warning "Release cancelled"
  git checkout pyproject.toml
  exit 1
fi

# Create release branch and commit
RELEASE_BRANCH="release/$NEW_VERSION"
print_step "Creating release branch: $RELEASE_BRANCH"
git checkout -b "$RELEASE_BRANCH"
git add pyproject.toml
git commit -m "release: $NEW_VERSION"

# Push branch and create PR
print_step "Pushing branch and creating PR"
git push origin "$RELEASE_BRANCH"

PR_URL=$(gh pr create \
  --title "release: $NEW_VERSION" \
  --label "internal" \
  --body "$(cat <<EOF
## Release $NEW_VERSION

Bumps version to \`$NEW_VERSION\` ($VERSION_TYPE release).

### After merge
1. Push to \`main\` triggers a **dev release** (pre-release to PyPI)
2. The \`release-tag\` workflow detects this merged release PR and creates tag \`$NEW_VERSION\`
3. Tag push triggers the **production release** (publish to PyPI, Docker, etc.)

### Checklist
- [ ] CI passes
- [ ] Version in \`pyproject.toml\` is correct (\`$NEW_VERSION\`)
EOF
)")

# Switch back to main
git checkout main

# Final success message
echo -e "\n${BOLD}${GREEN}Release PR created successfully!${NC}\n"
echo -e "  PR: $PR_URL"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "  1. Get the PR reviewed and merged"
echo "  2. After merge, the tag will be created automatically"
echo "  3. Monitor the release: https://github.com/marimo-team/marimo/actions/workflows/release.yml"
