# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "msgspec",
# ]
#
# [tool.uv]
# exclude-newer = "2025-06-27T12:38:25.742953-04:00"
# ///
"""Generate release notes from commits on main branch."""

from __future__ import annotations

import re
import subprocess
import sys

import msgspec


class Author(msgspec.Struct):
    """GitHub author/user information."""

    login: str


class Label(msgspec.Struct):
    """GitHub label information."""

    name: str
    color: str | None = None
    description: str | None = None


class PullRequest(msgspec.Struct):
    """GitHub Pull Request information."""

    number: int
    title: str
    author: Author
    labels: list[Label]
    body: str | None
    mergedAt: str | None = None


class Commit(msgspec.Struct):
    """Git commit information."""

    sha: str
    message: str
    pr_number: int | None = None


class CategorizedEntry(msgspec.Struct):
    """A release note entry with its PR information."""

    commit: Commit
    pr: PullRequest | None = None


def get_commits_since_tag(since_tag: str) -> list[Commit]:
    """Get commits on main since a specific tag."""
    result = subprocess.run(
        [
            "git",
            "log",
            f"{since_tag}..HEAD",
            "--format=%H %s",
            "--first-parent",  # Only follow the first parent (main branch)
            "main",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue

        sha, message = parts

        # Extract PR number from squash merge commit message
        # Looking for patterns like (#1234) or #1234
        pr_match = re.search(r"#(\d+)", message)
        pr_number = int(pr_match.group(1)) if pr_match else None

        commits.append(Commit(sha=sha, message=message, pr_number=pr_number))

    return commits


def get_merged_prs(limit: int = 100) -> dict[int, PullRequest]:
    """Get recently merged PRs and return as a dict keyed by PR number."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--base",
            "main",
            "--state",
            "merged",
            "--limit",
            str(limit),
            "--json",
            "number,title,author,labels,body,mergedAt",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        pr.number: pr
        for pr in msgspec.json.decode(result.stdout, type=list[PullRequest])
    }


def extract_media_from_body(body: str | None) -> list[str]:
    """Extract media (images/links) from PR body."""
    if not body:
        return []

    media = []

    # Find markdown images: ![alt](url)
    img_pattern = r"!\[.*?\]\((.*?)\)"
    for match in re.finditer(img_pattern, body):
        media.append(f'<img src="{match.group(1)}" alt="PR media">')

    # Find HTML img tags
    html_img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    for match in re.finditer(html_img_pattern, body):
        media.append(match.group(0))

    # Find video links (common patterns)
    video_patterns = [
        r"https?://[^\s]+\.(?:mp4|webm|mov|gif)",
        r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^\s]+",
        r"https?://(?:www\.)?vimeo\.com/[^\s]+",
    ]
    for pattern in video_patterns:
        for match in re.finditer(pattern, body):
            media.append(f'<a href="{match.group(0)}">{match.group(0)}</a>')

    return media


def categorize_entries(
    entries: list[CategorizedEntry],
) -> dict[str, list[CategorizedEntry]]:
    """Categorize entries based on PR labels."""
    # TODO: Could add more or be more granular
    categories = {
        "bug": [],
        "enhancement": [],
        "preview": [],
        "other": [],
        "highlights": [],
    }

    for entry in entries:
        if entry.pr is None:
            categories["other"].append(entry)
            continue

        label_names = {label.name for label in entry.pr.labels}

        if "release-highlight" in label_names:
            categories["highlights"].append(entry)

        if "bug" in label_names:
            categories["bug"].append(entry)
        elif "enhancement" in label_names:
            categories["enhancement"].append(entry)
        elif "preview" in label_names:
            categories["preview"].append(entry)
        else:
            categories["other"].append(entry)

    return categories


def strip_conventional_prefix(title: str) -> str:
    """Strip conventional commit prefixes and capitalize first letter."""
    # Match patterns like "word:" or "word(scope):" at the beginning
    match = re.match(r"^(\w+)(?:\([^)]+\))?:\s*(.+)", title)
    if match:
        # Get the part after the prefix and capitalize first letter
        stripped = match.group(2)
        return stripped[0].upper() + stripped[1:] if stripped else stripped
    return title


def format_entry(entry: CategorizedEntry) -> str:
    if entry.pr:
        title = strip_conventional_prefix(entry.pr.title)
        return f"* {title} ([#{entry.pr.number}](https://github.com/marimo-team/marimo/pull/{entry.pr.number}))"
    title = entry.commit.message
    title = strip_conventional_prefix(entry.commit.message)
    return f"* {title} ({entry.commit.sha[:7]})"


def generate_release_notes(since_tag: str) -> str:
    """Generate release notes since a specific tag."""
    commits = get_commits_since_tag(since_tag)
    pr_map = get_merged_prs(limit=100)

    # Match commits with PRs
    entries = []
    for commit in commits:
        pr = pr_map.get(commit.pr_number) if commit.pr_number else None
        entries.append(CategorizedEntry(commit=commit, pr=pr))

    categories = categorize_entries(entries)

    notes = ["## What's Changed\n"]
    if categories["highlights"]:
        for i, entry in enumerate(categories["highlights"]):
            if i > 0:
                notes.append("")

            if entry.pr:
                notes.append(f"**TODO: {entry.pr.title}**")
                notes.append("")
                notes.append("TODO: Description of the feature")

                # Check for media
                label_names = {label.name for label in entry.pr.labels}
                if "includes-media" in label_names:
                    media = extract_media_from_body(entry.pr.body)
                    if media:
                        notes.append("")
                        for item in media:
                            notes.append(item)
                notes.append("")

    if categories["enhancement"]:
        notes.append("## ✨ Enhancements")
        for entry in categories["enhancement"]:
            notes.append(format_entry(entry))
        notes.append("")

    if categories["preview"]:
        notes.append("## 🔬 Preview features")
        for entry in categories["preview"]:
            notes.append(format_entry(entry))
        notes.append("")

    if categories["bug"]:
        notes.append("## 🐛 Bug fixes")
        for entry in categories["bug"]:
            notes.append(format_entry(entry))
        notes.append("")

    if categories["other"]:
        notes.append("## 📝 Other")
        for entry in categories["other"]:
            notes.append(format_entry(entry))
        notes.append("")

    notes.append("## New Contributors")
    notes.append("* TODO: Check for new contributors")

    current_tag = "TODO_CURRENT_VERSION"
    notes.append(
        f"\n**Full Changelog**: https://github.com/marimo-team/marimo/compare/{since_tag}...{current_tag}"
    )

    return "\n".join(notes)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: generate_release_notes.py <since-tag>")
        print("Example: generate_release_notes.py 0.14.7")
        sys.exit(1)

    print(generate_release_notes(sys.argv[1]))


if __name__ == "__main__":
    main()
