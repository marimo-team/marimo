# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "msgspec",
# ]
#
# [tool.uv]
# exclude-newer = "2025-06-27T12:38:25.742953-04:00"
# ///
"""Get GitHub PRs labeled with 'bash-focus' since the last release."""

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
    url: str
    mergedAt: str | None = None


def get_latest_tag() -> str:
    """Get the latest git tag."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_commits_since_tag(since_tag: str) -> set[int]:
    """Get PR numbers from commits since a specific tag."""
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"{since_tag}..HEAD",
                "--format=%s",
                "--first-parent",
                "main",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print(f"Error: Tag '{since_tag}' not found. Available tags:")
        tag_result = subprocess.run(
            ["git", "tag", "--list", "--sort=-version:refname"],
            capture_output=True,
            text=True,
        )
        for tag in tag_result.stdout.strip().split('\n')[:10]:
            print(f"  {tag}")
        sys.exit(1)
    
    pr_numbers = set()
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        # Extract PR number from commit message
        pr_match = re.search(r'#(\d+)', line)
        if pr_match:
            pr_numbers.add(int(pr_match.group(1)))
    
    return pr_numbers


def get_prs_with_label(label: str, pr_numbers: set[int]) -> list[PullRequest]:
    """Get PRs with specific label from a set of PR numbers."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--base",
            "main",
            "--state",
            "merged",
            "--label",
            label,
            "--limit",
            "100",
            "--json",
            "number,title,author,labels,url,mergedAt",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    
    all_prs = msgspec.json.decode(result.stdout, type=list[PullRequest])
    
    # Filter PRs that are in our commit list
    filtered_prs = [pr for pr in all_prs if pr.number in pr_numbers]
    
    return filtered_prs


def main() -> None:
    label = "bash-focus"
    
    # Allow specifying a tag or use the latest one
    if len(sys.argv) >= 2:
        since_tag = sys.argv[1]
    else:
        since_tag = get_latest_tag()
        print(f"Using latest tag: {since_tag}")
    
    print(f"Fetching PRs with label '{label}' since {since_tag}...\n")
    
    pr_numbers = get_commits_since_tag(since_tag)
    prs = get_prs_with_label(label, pr_numbers)
    
    if not prs:
        print(f"No PRs found with label '{label}' since {since_tag}")
        return
    
    print(f"Found {len(prs)} PR(s) with label '{label}':\n")
    
    for pr in prs:
        print(f"#{pr.number}: {pr.title}")
        print(f"  Author: @{pr.author.login}")
        print(f"  Link: {pr.url}")
        print(f"  Merged: {pr.mergedAt}")
        print()


if __name__ == "__main__":
    main()
