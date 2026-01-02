# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from marimo._utils.config.config import ConfigReader


@dataclass
class MarimoCLIState:
    latest_version: Optional[str] = None
    last_checked_at: Optional[str] = None
    accepted_text_to_notebook_terms_at: Optional[str] = None
    notices: Optional[list[str]] = None


FILE_NAME = "state.toml"


def get_cli_state() -> MarimoCLIState:
    config_reader = ConfigReader.for_filename(FILE_NAME)
    # Load the state file or create a default state if it doesn't exist
    state = config_reader.read_toml(MarimoCLIState, fallback=MarimoCLIState())
    return state


def write_cli_state(state: MarimoCLIState) -> None:
    config_reader = ConfigReader.for_filename(FILE_NAME)
    config_reader.write_toml(state)
