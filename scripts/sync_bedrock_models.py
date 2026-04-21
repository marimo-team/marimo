# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "marimo",
#     "pyyaml",
# ]
# ///
"""Sync marimo's Bedrock model catalog with the latest models available on AWS.

Run from the repo root:

    uv run --with boto3 --with pyyaml marimo edit scripts/sync_bedrock_models.py

Requires AWS credentials with `bedrock:ListFoundationModels` and
`bedrock:ListInferenceProfiles` permissions.
"""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    # Sync AWS Bedrock Models

    This notebook compares the Bedrock models defined in
    `packages/llm-info/data/models.yml` with the models currently available
    in AWS Bedrock, and helps detect stale or missing entries.
    """
    )
    return


@app.cell
def _(mo):
    region = mo.ui.dropdown(
        options=[
            "us-east-1",
            "us-west-2",
            "us-east-2",
            "eu-central-1",
            "eu-west-1",
            "ap-northeast-1",
            "ap-southeast-1",
        ],
        value="us-west-2",
        label="AWS Region",
    )
    profile = mo.ui.text(
        value="",
        label="AWS Profile (optional)",
        placeholder="Leave empty for default credentials",
    )
    providers = mo.ui.multiselect(
        options=["anthropic", "amazon", "meta", "cohere", "mistral", "ai21"],
        value=["anthropic", "meta", "cohere"],
        label="Providers to query",
    )
    mo.hstack([region, profile, providers], justify="start")
    return profile, providers, region


@app.cell
def _(profile, providers, region):
    import boto3

    session_kwargs = {"region_name": region.value}
    if profile.value.strip():
        session_kwargs["profile_name"] = profile.value.strip()

    session = boto3.Session(**session_kwargs)
    client = session.client("bedrock")

    foundation_models: list[dict] = []
    for provider in providers.value:
        resp = client.list_foundation_models(byProvider=provider)
        foundation_models.extend(resp.get("modelSummaries", []))

    inference_profiles: list[dict] = []
    paginator = client.get_paginator("list_inference_profiles")
    for page in paginator.paginate():
        inference_profiles.extend(page.get("inferenceProfileSummaries", []))
    return foundation_models, inference_profiles


@app.cell
def _(foundation_models, inference_profiles, mo):
    import pandas as pd

    fm_df = pd.DataFrame(
        [
            {
                "modelId": m["modelId"],
                "modelName": m.get("modelName"),
                "providerName": m.get("providerName"),
                "inputModalities": ", ".join(m.get("inputModalities", [])),
                "outputModalities": ", ".join(m.get("outputModalities", [])),
                "lifecycleStatus": m.get("modelLifecycle", {}).get("status"),
            }
            for m in foundation_models
        ]
    ).sort_values("modelId")

    ip_df = pd.DataFrame(
        [
            {
                "inferenceProfileId": p.get("inferenceProfileId"),
                "inferenceProfileName": p.get("inferenceProfileName"),
                "status": p.get("status"),
                "type": p.get("type"),
            }
            for p in inference_profiles
        ]
    ).sort_values("inferenceProfileId")

    mo.vstack(
        [
            mo.md("### Foundation models"),
            mo.ui.table(fm_df, selection=None),
            mo.md("### Inference profiles (cross-region entry points)"),
            mo.ui.table(ip_df, selection=None),
        ]
    )
    return fm_df, ip_df


@app.cell
def _():
    from pathlib import Path

    import yaml

    repo_root = Path(__file__).resolve().parent.parent
    models_path = repo_root / "packages" / "llm-info" / "data" / "models.yml"
    marimo_models = yaml.safe_load(models_path.read_text())
    marimo_bedrock = [
        m for m in marimo_models if "bedrock" in m.get("providers", [])
    ]
    return marimo_bedrock, models_path


@app.cell
def _(fm_df, ip_df, marimo_bedrock, mo):
    available_ids = set(fm_df["modelId"]) | set(ip_df["inferenceProfileId"])

    def strip_region_prefix(model_id: str) -> str:
        # inference profiles are prefixed with "global.", "us.", "eu.", "apac.", ...
        parts = model_id.split(".", 1)
        if len(parts) == 2 and len(parts[0]) <= 5 and parts[0].islower():
            return parts[1]
        return model_id

    rows = []
    for entry in marimo_bedrock:
        model_id = entry["model"]
        exact = model_id in available_ids
        base = strip_region_prefix(model_id)
        base_match = not exact and any(
            base == strip_region_prefix(aid) for aid in available_ids
        )
        rows.append(
            {
                "name": entry["name"],
                "model": model_id,
                "exact_match": exact,
                "base_match_only": base_match,
                "status": "ok"
                if exact
                else ("needs region prefix adjustment" if base_match else "MISSING"),
            }
        )

    import pandas as pd

    marimo_df = pd.DataFrame(rows)
    stale = marimo_df[marimo_df["status"] != "ok"]

    mo.vstack(
        [
            mo.md("### marimo Bedrock catalog vs AWS"),
            mo.ui.table(marimo_df, selection=None),
            mo.md(f"**Stale or missing entries:** {len(stale)}"),
            mo.ui.table(stale, selection=None) if len(stale) else mo.md("All good ✓"),
        ]
    )
    return (marimo_df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ### How to update

    1. Use the tables above to find new or renamed model IDs.
    2. Edit `packages/llm-info/data/models.yml`.
    3. Run `pnpm --filter @marimo-team/llm-info codegen` to regenerate JSON.
    4. Run `pnpm --filter @marimo-team/llm-info test`.
    """
    )
    return


if __name__ == "__main__":
    app.run()
