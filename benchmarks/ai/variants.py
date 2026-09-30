from __future__ import annotations

from benchmarks.ai.models import HarnessVariant

VARIANTS = (
    HarnessVariant(
        id="baseline",
        description="Current production code-mode harness and prompts.",
    ),
    HarnessVariant(
        id="hybrid_balanced",
        description=(
            "Atomic hybrid tools plus grouped package, UI-state, and cell "
            "configuration capabilities."
        ),
        tool_strategy="hybrid_balanced",
        history_strategy="semantic",
    ),
    HarnessVariant(
        id="hybrid_uncompacted",
        description=(
            "Evaluation control retaining complete conversation history."
        ),
        tool_strategy="hybrid_balanced",
    ),
    HarnessVariant(
        id="hybrid_checkpoint",
        description=(
            "Adaptive seven-tool hybrid: semantic trimming normally, with "
            "incremental checkpoints after the long-history threshold."
        ),
        tool_strategy="hybrid_balanced",
        history_strategy="incremental_checkpoint",
        checkpoint_threshold_chars=60_000,
    ),
)


def get_variants(ids: set[str] | None = None) -> tuple[HarnessVariant, ...]:
    if not ids:
        return (VARIANTS[0],)
    variants = tuple(variant for variant in VARIANTS if variant.id in ids)
    missing = ids - {variant.id for variant in variants}
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Unknown variant(s): {names}")
    return variants
