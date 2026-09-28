# Copyright 2026 Marimo. All rights reserved.
"""The bundled template catalog."""

from __future__ import annotations

import re
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import msgspec

from marimo._convert.converters import MarimoConvert
from marimo._utils.paths import marimo_package_path

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SCRIPT_METADATA_PATTERN = re.compile(r"(?m)^# /// script\r?$")
_LAUNCH_KEY_PREFIX = "__marimo_template__"
_DEFAULT_LAUNCH_TTL_SECONDS = 5 * 60
_DEFAULT_MAX_LAUNCHES = 100


class CatalogValidationError(ValueError):
    """The bundled template catalog is invalid."""


class TemplateNotFoundError(KeyError):
    """A template ID is not present in the catalog."""


class TemplateLaunchNotFoundError(KeyError):
    """A template launch key is invalid or expired."""


@dataclass(frozen=True)
class CatalogCategory:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    title: str
    description: str
    category_ids: tuple[str, ...]
    notebook_path: Path
    preview_path: Path


@dataclass(frozen=True)
class _TemplateLaunch:
    source: str
    expires_at: float


class _ManifestCategory(msgspec.Struct, forbid_unknown_fields=True):
    id: str
    title: str
    description: str


class _ManifestEntry(msgspec.Struct, forbid_unknown_fields=True):
    id: str
    notebook: str
    title: str
    description: str
    categories: list[str]
    preview: str | None = None


class _Manifest(msgspec.Struct, forbid_unknown_fields=True):
    categories: list[_ManifestCategory]
    featured: list[str]
    templates: list[_ManifestEntry]


class TemplateCatalog:
    """A validated catalog backed by bundled files."""

    def __init__(
        self,
        *,
        categories: tuple[CatalogCategory, ...],
        entries: tuple[CatalogEntry, ...],
        featured_ids: tuple[str, ...],
    ) -> None:
        self.categories = categories
        self.entries = entries
        self.featured_ids = featured_ids
        self._entries_by_id = {entry.id: entry for entry in entries}

    @classmethod
    def from_directory(
        cls,
        root: Path,
        *,
        fallback_preview: Path | None = None,
    ) -> TemplateCatalog:
        """Read and validate a catalog directory."""
        root = root.resolve()
        manifest_path = root / "catalog.json"
        fallback_preview = (
            fallback_preview or marimo_package_path() / "_static" / "logo.png"
        ).resolve()

        try:
            manifest = msgspec.json.decode(
                manifest_path.read_bytes(), type=_Manifest
            )
        except (OSError, msgspec.DecodeError) as error:
            raise CatalogValidationError(
                f"Cannot read template catalog {manifest_path}: {error}"
            ) from error

        if not fallback_preview.is_file():
            raise CatalogValidationError(
                f"Fallback preview does not exist: {fallback_preview}"
            )

        categories = tuple(
            CatalogCategory(
                id=category.id,
                title=category.title,
                description=category.description,
            )
            for category in manifest.categories
        )
        _validate_categories(categories)
        category_ids = {category.id for category in categories}

        entries = tuple(
            _load_entry(
                root,
                entry,
                category_ids=category_ids,
                fallback_preview=fallback_preview,
            )
            for entry in manifest.templates
        )
        _validate_unique_ids(
            (entry.id for entry in entries), item_name="template"
        )

        entry_ids = {entry.id for entry in entries}
        _validate_unique_ids(manifest.featured, item_name="featured template")
        unknown_featured = set(manifest.featured) - entry_ids
        if unknown_featured:
            ids = ", ".join(sorted(unknown_featured))
            raise CatalogValidationError(
                f"Featured template IDs are not in the catalog: {ids}"
            )

        return cls(
            categories=categories,
            entries=entries,
            featured_ids=tuple(manifest.featured),
        )

    def get(self, template_id: str) -> CatalogEntry:
        try:
            return self._entries_by_id[template_id]
        except KeyError as error:
            raise TemplateNotFoundError(template_id) from error


class TemplateManager:
    """Provides catalog access and short-lived template launches."""

    def __init__(
        self,
        catalog: TemplateCatalog | None = None,
        *,
        launch_ttl_seconds: float = _DEFAULT_LAUNCH_TTL_SECONDS,
        max_launches: int = _DEFAULT_MAX_LAUNCHES,
        clock: Callable[[], float] = time.monotonic,
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        if launch_ttl_seconds <= 0:
            raise ValueError("Template launch lifetime must be positive")
        if max_launches <= 0:
            raise ValueError("Template launch limit must be positive")
        self.catalog = catalog or load_default_catalog()
        self._launch_ttl_seconds = launch_ttl_seconds
        self._max_launches = max_launches
        self._clock = clock
        self._token_factory = token_factory
        self._launches: OrderedDict[str, _TemplateLaunch] = OrderedDict()
        self._lock = threading.Lock()

    def create_launch(self, template_id: str) -> str:
        """Create an opaque launch key for a bundled template."""
        entry = self.catalog.get(template_id)
        source = entry.notebook_path.read_text(encoding="utf-8")
        now = self._clock()
        with self._lock:
            self._remove_expired(now)
            while len(self._launches) >= self._max_launches:
                self._launches.popitem(last=False)
            key = self._new_launch_key()
            self._launches[key] = _TemplateLaunch(
                source=source,
                expires_at=now + self._launch_ttl_seconds,
            )
        return key

    def resolve_launch(self, key: str) -> str | None:
        """Return template source for a launch key, or `None` for other keys."""
        if not key.startswith(_LAUNCH_KEY_PREFIX):
            return None
        now = self._clock()
        with self._lock:
            self._remove_expired(now)
            launch = self._launches.get(key)
            if launch is None:
                raise TemplateLaunchNotFoundError(key)
            return launch.source

    def consume_launch(self, key: str) -> None:
        """Remove a launch after a session takes ownership of its notebook."""
        if not key.startswith(_LAUNCH_KEY_PREFIX):
            return
        with self._lock:
            self._launches.pop(key, None)

    def _new_launch_key(self) -> str:
        while True:
            key = f"{_LAUNCH_KEY_PREFIX}{self._token_factory()}"
            if key not in self._launches:
                return key

    def _remove_expired(self, now: float) -> None:
        expired = [
            key
            for key, launch in self._launches.items()
            if launch.expires_at <= now
        ]
        for key in expired:
            del self._launches[key]


def _validate_categories(categories: tuple[CatalogCategory, ...]) -> None:
    if not categories:
        raise CatalogValidationError(
            "Template catalog must define at least one category"
        )
    _validate_unique_ids(
        (category.id for category in categories), item_name="category"
    )
    for category in categories:
        _validate_id(category.id, item_name="category")
        _validate_text(category.title, field="title", item_id=category.id)
        _validate_text(
            category.description,
            field="description",
            item_id=category.id,
        )


def _load_entry(
    root: Path,
    entry: _ManifestEntry,
    *,
    category_ids: set[str],
    fallback_preview: Path,
) -> CatalogEntry:
    _validate_id(entry.id, item_name="template")
    _validate_text(entry.title, field="title", item_id=entry.id)
    _validate_text(entry.description, field="description", item_id=entry.id)
    if not entry.categories:
        raise CatalogValidationError(
            f"Template {entry.id!r} must have at least one category"
        )
    _validate_unique_ids(
        entry.categories,
        item_name=f"category on template {entry.id!r}",
    )
    unknown_categories = set(entry.categories) - category_ids
    if unknown_categories:
        ids = ", ".join(sorted(unknown_categories))
        raise CatalogValidationError(
            f"Template {entry.id!r} uses unknown categories: {ids}"
        )

    notebook_path = _resolve_resource(
        root,
        entry.notebook,
        item_id=entry.id,
        field="notebook",
    )
    if notebook_path.suffix != ".py":
        raise CatalogValidationError(
            f"Template {entry.id!r} notebook must be a Python file"
        )
    source = notebook_path.read_text(encoding="utf-8")
    if _SCRIPT_METADATA_PATTERN.search(source):
        raise CatalogValidationError(
            f"Template {entry.id!r} must not contain PEP 723 metadata"
        )
    try:
        notebook = MarimoConvert.from_py(source).to_ir()
    except Exception as error:
        raise CatalogValidationError(
            f"Template {entry.id!r} is not a valid marimo notebook: {error}"
        ) from error
    if not notebook.valid:
        raise CatalogValidationError(
            f"Template {entry.id!r} is not a valid marimo notebook"
        )

    preview_path = fallback_preview
    if entry.preview is not None:
        preview_path = _resolve_resource(
            root,
            entry.preview,
            item_id=entry.id,
            field="preview",
        )
        if preview_path.suffix.lower() != ".png":
            raise CatalogValidationError(
                f"Template {entry.id!r} preview must be a PNG file"
            )

    return CatalogEntry(
        id=entry.id,
        title=entry.title,
        description=entry.description,
        category_ids=tuple(entry.categories),
        notebook_path=notebook_path,
        preview_path=preview_path,
    )


def _resolve_resource(
    root: Path,
    relative_path: str,
    *,
    item_id: str,
    field: str,
) -> Path:
    if not relative_path.strip():
        raise CatalogValidationError(
            f"Template {item_id!r} has an empty {field} path"
        )
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise CatalogValidationError(
            f"Template {item_id!r} {field} must stay inside the catalog"
        )
    if not path.is_file():
        raise CatalogValidationError(
            f"Template {item_id!r} {field} does not exist: {relative_path}"
        )
    return path


def _validate_unique_ids(ids: Iterable[str], *, item_name: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            duplicates.add(item_id)
        seen.add(item_id)
    if duplicates:
        values = ", ".join(sorted(duplicates))
        raise CatalogValidationError(f"Duplicate {item_name} IDs: {values}")


def _validate_id(item_id: str, *, item_name: str) -> None:
    if not _ID_PATTERN.fullmatch(item_id):
        raise CatalogValidationError(
            f"Invalid {item_name} ID {item_id!r}; use lowercase kebab-case"
        )


def _validate_text(value: str, *, field: str, item_id: str) -> None:
    if not value.strip():
        raise CatalogValidationError(
            f"Catalog item {item_id!r} has an empty {field}"
        )


@lru_cache(maxsize=1)
def load_default_catalog() -> TemplateCatalog:
    return TemplateCatalog.from_directory(
        marimo_package_path() / "_template_catalog"
    )
