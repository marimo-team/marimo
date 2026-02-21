# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, cast
from urllib.parse import urlparse

import msgspec

from marimo import _loggers
from marimo._utils.paths import normalize_path
from marimo._utils.scripts import read_pyproject_from_script

LOGGER = _loggers.marimo_logger()

DEFAULT_OPENGRAPH_IMAGE_FILENAME = "opengraph.png"
_WORD_SPLIT_RE = re.compile(r"[_-]+")
_MARIMO_GREEN = "#59b39a"


class OpenGraphMetadata(msgspec.Struct, rename="camel"):
    """OpenGraph-style metadata for a notebook.

    The `image` field may be either:
    - a relative path (typically under `__marimo__/`), or
    - an absolute HTTPS URL.
    """

    title: str | None = None
    description: str | None = None
    image: str | None = None


@dataclass(frozen=True)
class OpenGraphConfig:
    """Declarative configuration for resolving notebook OpenGraph metadata."""

    title: str | None = None
    description: str | None = None
    image: str | None = None
    generator: str | None = None


def _maybe_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def is_https_url(value: str) -> bool:
    """Return True if value is an absolute HTTPS URL."""
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme == "https" and bool(parsed.netloc)


def _normalize_opengraph_image(value: str | None) -> str | None:
    """Normalize an opengraph image value to a safe path (typically under `__marimo__/`) or HTTPS URL."""
    if value is None:
        return None
    if is_https_url(value):
        return value

    # Disallow URLs with other schemes (e.g. http, data, file).
    parsed = urlparse(value)
    if parsed.scheme:
        return None

    path = Path(value)
    if path.is_absolute():
        return None
    return value


OpenGraphMode = Literal["run", "edit"]


@dataclass(frozen=True)
class OpenGraphContext:
    """Context passed to OpenGraph generator functions."""

    filepath: str
    # File router key (often a workspace-relative path); may be None.
    file_key: str | None = None
    # Server base URL (e.g. http://localhost:2718); may be None in CLI contexts.
    base_url: str | None = None
    mode: OpenGraphMode | None = None


OpenGraphGeneratorReturn = OpenGraphMetadata | dict[str, Any] | None
OpenGraphGenerator = Callable[..., OpenGraphGeneratorReturn]
OpenGraphGeneratorArity = Literal[0, 1, 2]


@dataclass(frozen=True)
class OpenGraphGeneratorSpec:
    fn: OpenGraphGenerator
    arity: OpenGraphGeneratorArity


def read_opengraph_from_pyproject(
    pyproject: dict[str, Any],
) -> OpenGraphConfig | None:
    """Extract OpenGraph metadata from a parsed PEP 723 pyproject dict."""
    tool = pyproject.get("tool")
    if not isinstance(tool, dict):
        return None
    marimo = tool.get("marimo")
    if not isinstance(marimo, dict):
        return None
    opengraph = marimo.get("opengraph")
    if not isinstance(opengraph, dict):
        return None

    config = OpenGraphConfig(
        title=_maybe_str(opengraph.get("title")),
        description=_maybe_str(opengraph.get("description")),
        image=_normalize_opengraph_image(_maybe_str(opengraph.get("image"))),
        generator=_maybe_str(opengraph.get("generator")),
    )

    if (
        config.title is None
        and config.description is None
        and config.image is None
        and config.generator is None
    ):
        return None
    return config


def read_opengraph_from_file(filepath: str) -> OpenGraphConfig | None:
    """Read OpenGraph metadata from a notebook's PEP 723 header."""
    try:
        script = Path(filepath).read_text(encoding="utf-8")
        project = read_pyproject_from_script(script) or {}
    except Exception:
        # Parsing errors are treated as "no metadata" so that listing and thumbnail generation don't spam warnings on malformed headers.
        return None
    return read_opengraph_from_pyproject(project)


def _title_case(text: str) -> str:
    return text[:1].upper() + text[1:].lower()


def derive_title_from_path(filepath: str) -> str:
    stem = Path(filepath).stem
    return " ".join(
        _title_case(part) for part in _WORD_SPLIT_RE.split(stem) if part
    )


def default_opengraph_image(filepath: str) -> str:
    """Return the default relative image path for a given notebook."""
    stem = Path(filepath).stem
    return f"__marimo__/assets/{stem}/{DEFAULT_OPENGRAPH_IMAGE_FILENAME}"


def _default_image_exists(filepath: str) -> bool:
    notebook_dir = normalize_path(Path(filepath)).parent
    return (notebook_dir / default_opengraph_image(filepath)).is_file()


def _merge_opengraph_metadata(
    parent: OpenGraphMetadata,
    override: OpenGraphMetadata | None,
) -> OpenGraphMetadata:
    """Merge two metadata objects with override values taking precedence."""
    if override is None:
        return parent

    def coalesce(a: Any, b: Any) -> Any:
        return a if a is not None else b

    return OpenGraphMetadata(
        title=coalesce(override.title, parent.title),
        description=coalesce(override.description, parent.description),
        image=coalesce(override.image, parent.image),
    )


def _coerce_opengraph_metadata(value: Any) -> OpenGraphMetadata | None:
    """Coerce a generator return value into OpenGraphMetadata."""
    if value is None:
        return None
    if isinstance(value, OpenGraphMetadata):
        return value
    if isinstance(value, dict):
        image = _maybe_str(value.get("image"))
        if image is None:
            image = _maybe_str(value.get("imageUrl"))
        return OpenGraphMetadata(
            title=_maybe_str(value.get("title")),
            description=_maybe_str(value.get("description")),
            image=_normalize_opengraph_image(image),
        )
    return None


def _parse_generator_signature(
    fn: OpenGraphGenerator, *, generator: str
) -> OpenGraphGeneratorSpec | None:
    """Validate a generator signature and return a normalized call spec."""
    if asyncio.iscoroutinefunction(fn):
        LOGGER.warning(
            "OpenGraph generator must be synchronous: %s", generator
        )
        return None
    try:
        sig = inspect.signature(fn)
    except Exception as e:
        LOGGER.warning(
            "Failed to inspect OpenGraph generator signature (%s): %s",
            generator,
            e,
        )
        return None

    params = tuple(sig.parameters.values())
    unsupported = tuple(
        param
        for param in params
        if param.kind
        in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    )
    if unsupported:
        LOGGER.warning(
            "OpenGraph generator signature must use 0-2 positional args: %s",
            generator,
        )
        return None

    positional = tuple(
        param
        for param in params
        if param.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    )
    if len(positional) > 2:
        LOGGER.warning(
            "OpenGraph generator signature must accept at most 2 args: %s",
            generator,
        )
        return None

    arity = cast(OpenGraphGeneratorArity, len(positional))
    return OpenGraphGeneratorSpec(fn=fn, arity=arity)


def _load_generator_from_module(
    module_spec: str, name: str, *, generator: str
) -> OpenGraphGeneratorSpec | None:
    try:
        module = importlib.import_module(module_spec)
    except Exception as e:
        LOGGER.warning("Failed to import OpenGraph generator module: %s", e)
        return None
    attr = getattr(module, name, None)
    if attr is None:
        LOGGER.warning(
            "OpenGraph generator %s not found in module %s", name, module_spec
        )
        return None
    if not callable(attr):
        LOGGER.warning("OpenGraph generator is not callable: %s", generator)
        return None
    return _parse_generator_signature(
        cast(OpenGraphGenerator, attr), generator=generator
    )


def _load_generator_from_notebook_source(
    notebook_path: str, name: str
) -> OpenGraphGeneratorSpec | None:
    """Load a generator function from the notebook source without executing it.

    We compile and exec a small synthetic module containing only:
    - import statements (so the generator can import deps)
    - the named function definition
    """
    try:
        source = Path(notebook_path).read_text(encoding="utf-8")
    except Exception as e:
        LOGGER.warning(
            "Failed to read notebook when loading OpenGraph generator: %s", e
        )
        return None

    try:
        module_ast = ast.parse(source, filename=notebook_path)
    except Exception as e:
        LOGGER.warning(
            "Failed to parse notebook when loading OpenGraph generator: %s", e
        )
        return None

    def is_setup_expr(expr: ast.expr) -> bool:
        if isinstance(expr, ast.Attribute):
            return (
                isinstance(expr.value, ast.Name)
                and expr.value.id == "app"
                and expr.attr == "setup"
            )
        if isinstance(expr, ast.Call):
            return is_setup_expr(expr.func)
        return False

    imports: list[ast.stmt] = []
    setup: list[ast.stmt] = []
    target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in module_ast.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
        elif isinstance(node, ast.With) and len(node.items) == 1:
            context_expr = node.items[0].context_expr
            if is_setup_expr(context_expr):
                # Inline the setup block body so that dependencies imported under `with app.setup:`
                # are available to the generator, without invoking marimo's setup cell registration.
                setup.extend(node.body)
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            target = node

    if target is None:
        LOGGER.warning(
            "OpenGraph generator %s not found in notebook %s",
            name,
            notebook_path,
        )
        return None

    # Ignore decorators so we don't execute notebook/app registration logic.
    # Metadata generators are treated as plain Python functions.
    if getattr(target, "decorator_list", None):
        target.decorator_list = []

    extracted = ast.Module(body=[*imports, *setup, target], type_ignores=[])
    ast.fix_missing_locations(extracted)
    namespace: dict[str, Any] = {}
    try:
        exec(compile(extracted, notebook_path, "exec"), namespace)  # noqa: S102
    except Exception as e:
        LOGGER.warning("Failed to exec OpenGraph generator stub: %s", e)
        return None
    fn = namespace.get(name)
    if not callable(fn):
        LOGGER.warning(
            "OpenGraph generator %s is not callable (in %s)",
            name,
            notebook_path,
        )
        return None
    return _parse_generator_signature(
        cast(OpenGraphGenerator, fn), generator=name
    )


def _load_opengraph_generator(
    generator: str, *, notebook_path: str
) -> OpenGraphGeneratorSpec | None:
    """Resolve a generator string into a callable.

    Supported forms:
    - "module.submodule:function"
    - "module.submodule.function"
    - "function_name" (loaded from notebook source via AST extraction)
    """
    value = generator.strip()
    if not value:
        return None

    module_spec: str | None
    name: str
    if ":" in value:
        module_spec, name = value.split(":", 1)
        module_spec = module_spec.strip()
        name = name.strip()
    elif "." in value:
        module_spec, name = value.rsplit(".", 1)
        module_spec = module_spec.strip()
        name = name.strip()
    else:
        return _load_generator_from_notebook_source(notebook_path, value)

    if not module_spec or not name:
        return None

    # Disallow filesystem-based generator specs to keep behavior predictable
    if (
        module_spec.endswith(".py")
        or "/" in module_spec
        or "\\" in module_spec
    ):
        LOGGER.warning(
            "OpenGraph generator must be importable as a Python module: %s",
            generator,
        )
        return None

    return _load_generator_from_module(module_spec, name, generator=generator)


def _call_opengraph_generator(
    spec: OpenGraphGeneratorSpec,
    *,
    context: OpenGraphContext,
    parent: OpenGraphMetadata,
) -> OpenGraphGeneratorReturn:
    """Invoke a generator with a stable calling convention."""
    if spec.arity == 2:
        return spec.fn(context, parent)
    if spec.arity == 1:
        return spec.fn(context)
    return spec.fn()


def _run_opengraph_generator(
    generator: str,
    *,
    context: OpenGraphContext,
    parent: OpenGraphMetadata,
) -> OpenGraphMetadata | None:
    spec = _load_opengraph_generator(generator, notebook_path=context.filepath)
    if spec is None:
        return None

    try:
        result = _call_opengraph_generator(
            spec, context=context, parent=parent
        )
    except Exception as e:
        LOGGER.warning("OpenGraph generator raised: %s", e)
        return None
    if inspect.isawaitable(result):
        # Avoid "coroutine was never awaited" warnings.
        close = getattr(result, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: S110
                pass
        LOGGER.warning(
            "OpenGraph generator returned an awaitable (must be sync): %s",
            generator,
        )
        return None

    dynamic = _coerce_opengraph_metadata(result)
    if dynamic is None:
        LOGGER.warning(
            "OpenGraph generator returned unsupported value: %s", type(result)
        )
        return None
    return dynamic


def resolve_opengraph_metadata(
    filepath: str,
    *,
    app_title: str | None = None,
    context: OpenGraphContext | None = None,
) -> OpenGraphMetadata:
    """Resolve OpenGraph metadata from config, defaults, and a generator hook."""
    declared = read_opengraph_from_file(filepath) or OpenGraphConfig()

    title = declared.title or app_title or derive_title_from_path(filepath)
    description = declared.description
    image = _normalize_opengraph_image(declared.image)
    if image is None and _default_image_exists(filepath):
        image = default_opengraph_image(filepath)

    resolved = OpenGraphMetadata(
        title=title,
        description=description,
        image=image,
    )

    if declared.generator:
        ctx = context or OpenGraphContext(filepath=filepath)
        dynamic = _run_opengraph_generator(
            declared.generator, context=ctx, parent=resolved
        )
        resolved = _merge_opengraph_metadata(resolved, dynamic)

    return resolved


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _wrap_title_lines(title: str, *, max_chars: int = 32) -> list[str]:
    words = title.split()
    if not words:
        return ["marimo"]

    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        extra = (1 if current else 0) + len(word)
        if current and current_len + extra > max_chars:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += extra

    if current:
        lines.append(" ".join(current))

    # Keep the placeholder compact.
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1].rstrip(".") + "..."

    return lines


@dataclass(frozen=True)
class OpenGraphImage:
    content: bytes
    media_type: str


@dataclass(frozen=True)
class DefaultOpenGraphPlaceholderImageGenerator:
    """Generate a deterministic placeholder thumbnail image."""

    width: int = 1200
    height: int = 630

    def __call__(self, title: str) -> OpenGraphImage:
        svg = self._render_svg(title)
        return OpenGraphImage(
            content=svg.encode("utf-8"),
            media_type="image/svg+xml",
        )

    def _render_svg(self, title: str) -> str:
        accent = _MARIMO_GREEN

        lines = _wrap_title_lines(title)
        escaped = [_xml_escape(line) for line in lines]

        # Center the title inside an inset card.
        card_x = 48
        card_y = 48
        card_w = self.width - 2 * card_x
        card_h = self.height - 2 * card_y
        stripe_w = 16

        line_height = 72
        block_height = line_height * len(escaped)
        start_y = card_y + int((card_h - block_height) / 2) + 56
        text_x = card_x + stripe_w + 36

        text_nodes: list[str] = []
        for i, line in enumerate(escaped):
            y = start_y + i * line_height
            text_nodes.append(
                f'<text x="{text_x}" y="{y}" font-size="60">{line}</text>'
            )

        text_svg = "\n    ".join(text_nodes)

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">
  <defs>
    <clipPath id="card">
      <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="24" />
    </clipPath>
  </defs>

  <rect width="{self.width}" height="{self.height}" fill="#f8fafc"/>
  <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="24" fill="#ffffff" stroke="#e2e8f0" stroke-width="2"/>
  <rect x="{card_x}" y="{card_y}" width="{stripe_w}" height="{card_h}" fill="{accent}" clip-path="url(#card)"/>

  <g fill="#0f172a" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial" font-weight="700">
    {text_svg}
  </g>

  <text x="{text_x}" y="{card_y + card_h - 32}" fill="#64748b" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="22" font-weight="600">
    marimo
  </text>
</svg>
"""


DEFAULT_OPENGRAPH_PLACEHOLDER_IMAGE_GENERATOR = (
    DefaultOpenGraphPlaceholderImageGenerator()
)
