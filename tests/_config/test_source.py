from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._config.config import (
    MarimoConfig,
    PartialMarimoConfig,
    merge_default_config,
)
from marimo._config.manager import (
    ConfigResolver,
    InMemoryConfigReader,
    MarimoConfigManager,
    PyprojectConfigReader,
    UserConfigStore,
)
from marimo._config.reader import read_marimo_config
from marimo._config.secrets import SECRET_PLACEHOLDER
from marimo._config.source import (
    ConfigReader,
    ConfigStore,
)

if TYPE_CHECKING:
    from pathlib import Path


def user_store(path: Path) -> UserConfigStore:
    class Store(UserConfigStore):
        def get_config_path(self) -> str:
            return str(path)

    return Store()


def test_project_secret_reads(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[tool.marimo.ai.open_ai]\napi_key = "secret"\n',
        encoding="utf-8",
    )
    source: ConfigReader = PyprojectConfigReader(str(tmp_path))
    for hide_secrets, key in [(True, SECRET_PLACEHOLDER), (False, "secret")]:
        assert source.read(hide_secrets=hide_secrets) == {
            "ai": {"open_ai": {"api_key": key}}
        }


def test_manager_accepts_source_with_only_read(tmp_path: Path) -> None:
    class Source:
        reads = 0

        def read(
            self, *, hide_secrets: bool = True
        ) -> PartialMarimoConfig | MarimoConfig:
            del hide_secrets
            self.reads += 1
            return {"display": {"theme": "dark"}}

    manager = MarimoConfigManager(user_store(tmp_path / "marimo.toml"))
    source = Source()
    layered = manager.with_reader(source)
    assert layered.get_config() == merge_default_config(
        {"display": {"theme": "dark"}}
    )
    assert source.reads == 1
    assert manager.get_config() == merge_default_config({})


def test_store_preserves_saving_behavior(tmp_path: Path) -> None:
    path = tmp_path / "marimo.toml"
    path.write_text('[ai.open_ai]\napi_key = "secret"\n', encoding="utf-8")
    store: ConfigStore = user_store(path)
    store.update(
        {"ai": {"max_tokens": 100, "open_ai": {"api_key": SECRET_PLACEHOLDER}}}
    )
    store.unset(("ai", "max_tokens"))
    expected = merge_default_config({"ai": {"open_ai": {"api_key": "secret"}}})
    assert read_marimo_config(str(path)) == expected
    assert store.read(hide_secrets=False) == expected


@pytest.mark.parametrize("path", [(), ("",), ("runtime", "")])
def test_unset_rejects_empty_paths(
    tmp_path: Path, path: tuple[str, ...]
) -> None:
    store = user_store(tmp_path / "marimo.toml")
    with pytest.raises(ValueError, match="non-empty keys"):
        store.unset(path)
    assert not (tmp_path / "marimo.toml").exists()


def test_user_source_is_sparse(tmp_path: Path) -> None:
    path = tmp_path / "marimo.toml"
    path.write_text('[display]\ntheme = "dark"\n', encoding="utf-8")
    store = user_store(path)
    assert store.read() == {"display": {"theme": "dark"}}
    assert store.get_config() == merge_default_config(
        {"display": {"theme": "dark"}}
    )


def test_user_source_uses_the_same_precedence_as_other_sources(
    tmp_path: Path,
) -> None:
    path = tmp_path / "marimo.toml"
    path.write_text('[display]\ntheme = "light"\n', encoding="utf-8")
    user = user_store(path)
    override = InMemoryConfigReader({"display": {"theme": "dark"}})
    assert MarimoConfigManager(
        user, override
    ).get_config() == merge_default_config({"display": {"theme": "dark"}})
    assert MarimoConfigManager(
        override, user
    ).get_config() == merge_default_config({"display": {"theme": "light"}})
    assert MarimoConfigManager().get_config() == merge_default_config({})
    assert MarimoConfigManager(override).get_config() == merge_default_config(
        {"display": {"theme": "dark"}}
    )


def test_unconfigured_user_fields_do_not_override_other_sources(
    tmp_path: Path,
) -> None:
    path = tmp_path / "marimo.toml"
    path.write_text("[save]\nautosave_delay = 2000\n", encoding="utf-8")
    override = InMemoryConfigReader({"display": {"theme": "dark"}})
    manager = MarimoConfigManager(override, user_store(path))
    assert manager.get_config() == merge_default_config(
        {"display": {"theme": "dark"}, "save": {"autosave_delay": 2000}}
    )


def test_user_and_project_views_remain_separate(tmp_path: Path) -> None:
    user_path = tmp_path / "user.toml"
    user_path.write_text('[display]\ntheme = "dark"\n', encoding="utf-8")
    project_path = tmp_path / "pyproject.toml"
    project_text = (
        '[tool.marimo.display]\ntheme = "light"\n'
        "[tool.marimo.formatting]\nline_length = 120\n"
    )
    project_path.write_text(project_text, encoding="utf-8")
    manager = MarimoConfigManager(
        user_store(user_path), PyprojectConfigReader(str(tmp_path))
    )
    assert manager.get_user_config() == merge_default_config(
        {"display": {"theme": "dark"}}
    )
    assert manager.get_config_overrides() == {
        "display": {"theme": "light", "custom_css": []},
        "formatting": {"line_length": 120},
    }
    manager.save_config({"display": {"theme": "dark"}})
    assert read_marimo_config(str(user_path)) == merge_default_config(
        {"display": {"theme": "dark"}}
    )
    assert project_path.read_text(encoding="utf-8") == project_text


def test_resolver_reads_without_a_store() -> None:
    resolver = ConfigResolver(
        InMemoryConfigReader({"display": {"theme": "dark"}})
    )
    assert resolver.get_config() == merge_default_config(
        {"display": {"theme": "dark"}}
    )
    assert resolver.theme == "dark"


def test_manager_delegates_resolution(tmp_path: Path) -> None:
    manager = MarimoConfigManager(user_store(tmp_path / "marimo.toml"))
    manager.resolver = ConfigResolver(
        InMemoryConfigReader({"display": {"theme": "dark"}})
    )
    assert manager.get_config() == manager.resolver.get_config()
    assert manager.resolver.theme == "dark"
