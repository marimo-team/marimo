# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import token as token_types
from dataclasses import dataclass
from tokenize import TokenError, tokenize
from typing import Callable


@dataclass
class CommentToken:
    text: str
    line: int
    col: int


class CommentPreserver:
    """Functor to preserve comments during source code transformations."""

    def __init__(self, sources: list[str]):
        self.sources = sources
        self.comments_by_source: dict[int, list[CommentToken]] = {}
        self._extract_all_comments()

    def _extract_all_comments(self) -> None:
        """Extract comments from all sources during initialization."""
        for i, source in enumerate(self.sources):
            self.comments_by_source[i] = self._extract_comments_from_source(
                source
            )

    def _extract_comments_from_source(self, source: str) -> list[CommentToken]:
        """Extract comments from a single source string."""
        if not source.strip():
            return []

        comments = []
        try:
            tokens = tokenize(io.BytesIO(source.encode("utf-8")).readline)
            for token in tokens:
                if token.type == token_types.COMMENT:
                    comments.append(
                        CommentToken(
                            text=token.string,
                            line=token.start[0],
                            col=token.start[1],
                        )
                    )
        except (TokenError, SyntaxError):
            # If tokenization fails, return empty list - no comments preserved
            pass

        return comments

    def __call__(
        self, transform_func: Callable[..., list[str]]
    ) -> Callable[..., list[str]]:
        """
        Method decorator that returns a comment-preserving version of transform_func.

        Usage: preserver(transform_func)(sources, *args, **kwargs)
        """

        def wrapper(*args: object, **kwargs: object) -> list[str]:
            # Apply the original transformation
            transformed_sources = transform_func(*args, **kwargs)

            # If sources weren't provided or transformation failed, return as-is
            if not args or not isinstance(args[0], list):
                return transformed_sources

            original_sources = args[0]

            # Merge comments back into transformed sources
            result = self._merge_comments(
                original_sources, transformed_sources
            )

            # Update our internal comment data to track only the clean transformed sources
            # This clears old comments that no longer apply
            self._update_comments_for_transformed_sources(transformed_sources)

            return result

        return wrapper

    def _merge_comments(
        self,
        original_sources: list[str],
        transformed_sources: list[str],
    ) -> list[str]:
        """Merge comments from original sources into transformed sources."""
        if len(original_sources) != len(transformed_sources):
            # If cell count changed, we can't preserve comments reliably
            return transformed_sources

        result = []
        for i, (original, transformed) in enumerate(
            zip(original_sources, transformed_sources)
        ):
            comments = self.comments_by_source.get(i, [])
            if not comments:
                result.append(transformed)
                continue

            # Apply comment preservation with variable name updates if needed
            preserved_source = self._apply_comments_to_source(
                original, transformed, comments
            )
            result.append(preserved_source)

        return result

    def _apply_comments_to_source(
        self,
        original: str,
        transformed: str,
        comments: list[CommentToken],
    ) -> str:
        """Apply comments to a single transformed source."""
        if not comments:
            return transformed

        original_lines = original.split("\n")
        transformed_lines = transformed.split("\n")

        # Create a mapping of line numbers to comments
        comments_by_line: dict[int, list[CommentToken]] = {}
        for comment in comments:
            line_num = comment.line
            if line_num not in comments_by_line:
                comments_by_line[line_num] = []
            comments_by_line[line_num].append(comment)

        # Apply comments to transformed lines
        result_lines = transformed_lines.copy()

        for line_num, line_comments in comments_by_line.items():
            target_line_idx = min(
                line_num - 1, len(result_lines) - 1
            )  # Convert to 0-based, clamp to bounds

            if target_line_idx < 0:
                continue

            # Select the best comment for this line (line comments take precedence)
            line_comment = None
            inline_comment = None

            for comment in line_comments:
                if comment.col == 0:  # Line comment (starts at column 0)
                    line_comment = comment
                    break  # Line comment takes precedence, no need to check others
                else:  # Inline comment
                    inline_comment = comment

            # Prefer line comment over inline comment
            chosen_comment = line_comment if line_comment else inline_comment

            if chosen_comment:
                comment_text = chosen_comment.text
                if chosen_comment.col > 0 and target_line_idx < len(
                    original_lines
                ):
                    # Inline comment - append to the line if not already present
                    current_line = result_lines[target_line_idx]
                    if not current_line.rstrip().endswith(
                        comment_text.rstrip()
                    ):
                        result_lines[target_line_idx] = (
                            current_line.rstrip() + "  " + comment_text
                        )
                elif target_line_idx >= 0 and comment_text not in result_lines:
                    # Standalone comment - insert above the line if not already present
                    result_lines.insert(target_line_idx, comment_text)

        return "\n".join(result_lines)

    def _update_comments_for_transformed_sources(
        self, sources: list[str]
    ) -> None:
        """Update internal comment data to track the transformed sources."""
        self.sources = sources
        self.comments_by_source = {}
        self._extract_all_comments()
