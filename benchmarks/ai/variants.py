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
            "Seven-tool hybrid with complete conversation history retained."
        ),
        tool_strategy="hybrid_balanced",
    ),
    HarnessVariant(
        id="hybrid_checkpoint",
        description=(
            "Seven-tool hybrid with semantic tool trimming and incremental "
            "completed-task checkpoints."
        ),
        tool_strategy="hybrid_balanced",
        history_strategy="incremental_checkpoint",
        checkpoint_threshold_chars=60_000,
    ),
    HarnessVariant(
        id="harness_checkpoint",
        description=(
            "Harness compact_now summaries persisted across sidebar turns."
        ),
        tool_strategy="hybrid_balanced",
        history_strategy="harness_checkpoint",
        checkpoint_threshold_chars=60_000,
    ),
    HarnessVariant(
        id="hybrid_checkpoint_forced",
        description=(
            "Custom persistent checkpoint forced at 25,000 characters for "
            "models with compact responses."
        ),
        tool_strategy="hybrid_balanced",
        history_strategy="incremental_checkpoint",
        checkpoint_threshold_chars=25_000,
    ),
    HarnessVariant(
        id="harness_checkpoint_forced",
        description=(
            "Harness persistent checkpoint forced at 25,000 characters for "
            "models with compact responses."
        ),
        tool_strategy="hybrid_balanced",
        history_strategy="harness_checkpoint",
        checkpoint_threshold_chars=25_000,
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
