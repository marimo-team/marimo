# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import msgspec


class TemplateCategory(msgspec.Struct, frozen=True, rename="camel"):
    id: str
    title: str
    description: str


class TemplateSummary(msgspec.Struct, frozen=True, rename="camel"):
    id: str
    title: str
    description: str
    category_ids: list[str]
    preview_url: str


class TemplateCatalogResponse(msgspec.Struct, frozen=True, rename="camel"):
    categories: list[TemplateCategory]
    templates: list[TemplateSummary]
    featured_ids: list[str]


class TemplateLaunchResponse(msgspec.Struct, frozen=True, rename="camel"):
    file_key: str
