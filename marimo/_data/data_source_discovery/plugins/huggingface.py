# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    environment_variable,
    has_value,
)
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)

# `huggingface_hub` reads `HF_TOKEN` first, falling back to the legacy
# `HUGGING_FACE_HUB_TOKEN` name.
# https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables#hftoken
# https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/utils/_auth.py
TOKEN_VARIABLES = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    token_name = next(
        (name for name in TOKEN_VARIABLES if has_value(environment, name)),
        None,
    )
    if token_name is None:
        return []

    return [
        DetectedDataSource(
            id="huggingface-hub-environment",
            integration="huggingface",
            category="object-storage",
            display_name="Hugging Face Hub",
            confidence="high",
            origins=(ENVIRONMENT_ORIGIN,),
            configuration=(environment_variable("Token", token_name),),
            code="""\
from huggingface_hub import HfApi

hf = HfApi()""",
        )
    ]


HUGGINGFACE_PLUGIN = DiscoveryPlugin(id="huggingface", discover=discover)
