/* Copyright 2026 Marimo. All rights reserved. */

import JsonView from "@uiw/react-json-view";
import { CheckIcon, CopyIcon } from "lucide-react";
import { memo, useCallback, useMemo, useState } from "react";
import type { OutputMessage } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { isUrl } from "@/utils/urls";
import { useTheme } from "../../../theme/useTheme";
import { logNever } from "../../../utils/assertNever";
import { OutputRenderer } from "../Output";
import { HtmlOutput } from "./HtmlOutput";
import { ImageOutput } from "./ImageOutput";
import { VideoOutput } from "./VideoOutput";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLLAPSED_TEXT_LENGTH = 100;
const PAGE_SIZE = 30;
const SMALL_CONTAINER = 8;
/** Sentinel prefix for "show more" markers injected into truncated data. */
const SHOW_MORE = "\x00show_more\x00";

// ---------------------------------------------------------------------------
// Themes — Solarized base16
// ---------------------------------------------------------------------------

const THEME_OVERRIDES = {
  fontSize: "var(--text-xs, .75rem)",
  lineHeight: "var(--text-xs--line-height, 1rem)",
  "--w-rjv-font-family": "monospace",
} as React.CSSProperties;

const marimoLightTheme: React.CSSProperties = {
  ...THEME_OVERRIDES,
  "--w-rjv-background-color": "transparent",
  "--w-rjv-color": "#002b36",
  "--w-rjv-key-string": "#002b36",
  "--w-rjv-key-number": "#6c71c4",
  "--w-rjv-line-color": "rgb(235, 235, 235)",
  "--w-rjv-arrow-color": "#002b36",
  "--w-rjv-info-color": "rgba(0, 0, 0, 0.3)",
  "--w-rjv-curlybraces-color": "#002b36",
  "--w-rjv-colon-color": "#002b36",
  "--w-rjv-brackets-color": "#002b36",
  "--w-rjv-ellipsis-color": "#cb4b16",
  "--w-rjv-quotes-color": "#002b36",
  "--w-rjv-quotes-string-color": "#cb4b16",
  "--w-rjv-type-string-color": "#cb4b16",
  "--w-rjv-type-int-color": "#268bd2",
  "--w-rjv-type-float-color": "#859900",
  "--w-rjv-type-bigint-color": "#268bd2",
  "--w-rjv-type-boolean-color": "#2aa198",
  "--w-rjv-type-date-color": "#586e75",
  "--w-rjv-type-url-color": "var(--link)",
  "--w-rjv-type-null-color": "#d33682",
  "--w-rjv-type-nan-color": "#d33682",
  "--w-rjv-type-undefined-color": "#586e75",
} as React.CSSProperties;

const marimoDarkTheme: React.CSSProperties = {
  ...THEME_OVERRIDES,
  "--w-rjv-background-color": "transparent",
  "--w-rjv-color": "#f8f8f8",
  "--w-rjv-key-string": "#f8f8f8",
  "--w-rjv-key-number": "#86c1b9",
  "--w-rjv-line-color": "#383838",
  "--w-rjv-arrow-color": "#f8f8f8",
  "--w-rjv-info-color": "#b8b8b8",
  "--w-rjv-curlybraces-color": "#f8f8f8",
  "--w-rjv-colon-color": "#f8f8f8",
  "--w-rjv-brackets-color": "#f8f8f8",
  "--w-rjv-ellipsis-color": "#dc9656",
  "--w-rjv-quotes-color": "#f8f8f8",
  "--w-rjv-quotes-string-color": "#dc9656",
  "--w-rjv-type-string-color": "#dc9656",
  "--w-rjv-type-int-color": "#a16946",
  "--w-rjv-type-float-color": "#a1b56c",
  "--w-rjv-type-bigint-color": "#a16946",
  "--w-rjv-type-boolean-color": "#ba8baf",
  "--w-rjv-type-date-color": "#7cafc2",
  "--w-rjv-type-url-color": "var(--link)",
  "--w-rjv-type-null-color": "#ab4642",
  "--w-rjv-type-nan-color": "#ab4642",
  "--w-rjv-type-undefined-color": "#d8d8d8",
} as React.CSSProperties;

// ---------------------------------------------------------------------------
// Small sub-components
// ---------------------------------------------------------------------------

const CopyButton: React.FC<{
  value: unknown;
  isPython: boolean;
  originals?: WeakMap<object, object>;
}> = ({ value, isPython, originals }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = async (evt: React.MouseEvent) => {
    evt.stopPropagation();
    // Resolve to original (untruncated) value for containers
    const resolved =
      value && typeof value === "object" && originals
        ? (originals.get(value) ?? value)
        : value;
    const text = isPython ? getCopyValue(resolved) : jsonCopyValue(resolved);
    await copyToClipboard(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };
  const Icon = copied ? CheckIcon : CopyIcon;
  return (
    <button
      onClick={handleCopy}
      className="inline-flex ml-2 copy-button rounded w-6 h-3 justify-center items-center relative"
      aria-label="Copy to clipboard"
      type="button"
    >
      <Icon className="w-5 h-5 absolute -top-0.5 p-1 hover:bg-muted rounded" />
    </button>
  );
};

// A span preserves inline wrapping; native buttons push long text and quotes
// onto separate lines. Keyboard activation is provided below.
/* oxlint-disable jsx-a11y/prefer-tag-over-role */
const CollapsibleTextOutput: React.FC<{ text: string }> = ({ text }) => {
  const [collapsed, setCollapsed] = useState(true);
  if (text.length <= COLLAPSED_TEXT_LENGTH) {
    return <span className="break-all">{text}</span>;
  }
  return (
    <span
      className="cursor-pointer hover:opacity-90 break-all"
      role="button"
      tabIndex={0}
      aria-expanded={!collapsed}
      onClick={() => setCollapsed(!collapsed)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setCollapsed(!collapsed);
        }
      }}
    >
      {collapsed ? `${text.slice(0, COLLAPSED_TEXT_LENGTH)}...` : text}
    </span>
  );
};

/* oxlint-enable jsx-a11y/prefer-tag-over-role */

// ---------------------------------------------------------------------------
// MIME / leaf rendering
// ---------------------------------------------------------------------------

type LeafRenderer = (
  data: string,
  mimeType: OutputMessage["mimetype"],
) => React.ReactNode;

const LEAF_RENDERERS: Record<string, LeafRenderer> = {
  "image/": (v) => <ImageOutput src={v} />,
  "video/": (v) => <VideoOutput src={v} />,
  "text/html:": (v) => (
    <HtmlOutput html={v} inline={true} alwaysSanitizeHtml={false} />
  ),
  "text/markdown:": (v) => (
    <HtmlOutput html={v} inline={true} alwaysSanitizeHtml={true} />
  ),
  "text/plain+float:": (v) => <span>{v}</span>,
  "text/plain+bigint:": (v) => <span>{v}</span>,
  "text/plain+set:": (v) => <span>{formatSetPayload(v)}</span>,
  "text/plain+frozenset:": (v) => <span>{formatFrozensetPayload(v)}</span>,
  "text/plain+tuple:": (v) => <span>{v}</span>,
  "text/plain:": (v) => <CollapsibleTextOutput text={v} />,
  "application/json:": (v) => <JsonOutput data={JSON.parse(v)} format="auto" />,
  "application/": (v, mime) => (
    <OutputRenderer
      message={{ channel: "output", data: v, mimetype: mime }}
      renderFallback={() => (
        <span>
          {mime}:{v}
        </span>
      )}
    />
  ),
};

const MIME_PREFIXES = Object.keys(LEAF_RENDERERS);

/** Split `<mime>:<data>` into `[data, mime]`. */
function splitLeaf(leaf: string): [string, string | undefined] {
  const idx = leaf.indexOf(":");
  return idx === -1
    ? [leaf, undefined]
    : [leaf.slice(idx + 1), leaf.slice(0, idx)];
}

function tryRenderMimeLeaf(value: string): React.ReactNode | null {
  for (const prefix of MIME_PREFIXES) {
    if (value.startsWith(prefix)) {
      const [data, mime] = splitLeaf(value);
      return mime
        ? LEAF_RENDERERS[prefix](data, mime as OutputMessage["mimetype"])
        : null;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Python collection payloads & encoded dict keys
// ---------------------------------------------------------------------------

// Prefix marking keys that carry encoded type information from Python.
// See `_key_formatter` in marimo/_output/formatters/structures.py.
const KEY_ENCODED_PREFIX = "text/plain+";
// The escape prefix for strings that merely *look* encoded; these keep
// their quotes and render as the original string.
const KEY_STR_PREFIX = "text/plain+str:";

// Format elements for a Python collection literal. Non-finite floats
// (NaN / Infinity / -Infinity) parse as JS `number` via
// `jsonParseWithSpecialChar`; `JSON.stringify` on those returns `null`,
// so render them as the same `float(...)` literals we use for scalar
// float keys (see `decodeKeyForCopy`).
function formatCollectionItems(items: unknown[]): string {
  return items
    .map((x) => {
      if (typeof x === "number" && !Number.isFinite(x)) {
        if (Number.isNaN(x)) {
          return "float('nan')";
        }
        return x > 0 ? "float('inf')" : "-float('inf')";
      }
      return JSON.stringify(x);
    })
    .join(", ");
}

// Format a JSON-list payload as a Python tuple literal. 1-element tuples
// need a trailing comma: `(1)` is just `1` in Python, `(1,)` is the tuple.
// Uses `jsonParseWithSpecialChar` so bare `NaN`/`Infinity`/`-Infinity`
// emitted by Python's json.dumps round-trip cleanly.
function formatTuplePayload(jsonList: string): string {
  const items = jsonParseWithSpecialChar<unknown[]>(jsonList);
  // `jsonParseWithSpecialChar` returns `{}` when both parse passes fail;
  // fall back to the raw payload so a malformed wire form doesn't crash
  // rendering/copy. Matches the defensive pattern in `formatSetPayload`.
  if (!Array.isArray(items)) {
    return jsonList;
  }
  if (items.length === 0) {
    return "()";
  }
  const inner = formatCollectionItems(items);
  if (items.length === 1) {
    return `(${inner},)`;
  }
  return `(${inner})`;
}

// Format a JSON-list payload as a Python frozenset literal. Empty → `frozenset()`
// rather than `frozenset({})` (which reads like a dict).
function formatFrozensetPayload(jsonList: string): string {
  const items = jsonParseWithSpecialChar<unknown[]>(jsonList);
  if (!Array.isArray(items)) {
    return jsonList;
  }
  if (items.length === 0) {
    return "frozenset()";
  }
  const inner = formatCollectionItems(items);
  return `frozenset({${inner}})`;
}

// Format a JSON-list payload as a Python set literal. Empty → `set()`
// (not `{}`, which is a dict literal in Python).
function formatSetPayload(jsonList: string): string {
  const items = jsonParseWithSpecialChar<unknown[]>(jsonList);
  if (!Array.isArray(items)) {
    // Back-compat: older wire form was `text/plain+set:{1, 2, 3}` (Python
    // set-literal string, not JSON). Pass it through as-is rather than crash.
    return jsonList;
  }
  if (items.length === 0) {
    return "set()";
  }
  const inner = formatCollectionItems(items);
  return `{${inner}}`;
}

// Renderers for decoded non-string keys. Visual affordances match Python:
// unquoted primitives, parens for tuple, `frozenset({...})` for frozenset.
// The `text/plain+str:` escape renders the original string; the viewer
// supplies its quotes (see `renderKeyQuote`).
const KEY_DECODERS: Record<string, (data: string) => React.ReactNode> = {
  "text/plain+int:": (v) => v,
  "text/plain+float:": (v) => v,
  "text/plain+bool:": (v) => (v === "True" ? "True" : "False"),
  "text/plain+none:": () => "None",
  "text/plain+tuple:": (v) => formatTuplePayload(v),
  "text/plain+frozenset:": (v) => formatFrozensetPayload(v),
  [KEY_STR_PREFIX]: (v) => v,
};

function isEncodedKey(key: unknown): key is string {
  return typeof key === "string" && key.startsWith(KEY_ENCODED_PREFIX);
}

/** Encoded keys other than the `str` escape render unquoted, like Python. */
function isUnquotedKey(key: unknown): key is string {
  return isEncodedKey(key) && !key.startsWith(KEY_STR_PREFIX);
}

interface KeyRenderResult {
  keyName?: string | number;
}

/** Render dict keys that carry Python type info (python mode only). */
function renderKeyName(
  props: Record<string, unknown>,
  { keyName }: KeyRenderResult,
): React.ReactNode {
  if (!isEncodedKey(keyName)) {
    return undefined;
  }
  const [data, mimeType] = splitLeaf(keyName);
  const render = KEY_DECODERS[`${mimeType}:`];
  const { children: _children, ...rest } =
    props as React.HTMLAttributes<HTMLSpanElement> & {
      children?: React.ReactNode;
    };
  return <span {...rest}>{render ? render(data) : keyName}</span>;
}

/** Suppress the viewer's key quotes for decoded (non-string) keys. */
function renderKeyQuote(
  _props: Record<string, unknown>,
  { keyName }: KeyRenderResult,
): React.ReactNode {
  // Returning an element (truthy) replaces the default quote with an empty
  // span; `undefined` would fall back to the default rendering.
  return isUnquotedKey(keyName) ? <span /> : undefined;
}

// ---------------------------------------------------------------------------
// Stable render callbacks (no deps — hoisted outside component)
// ---------------------------------------------------------------------------

interface RenderResult {
  type: string;
  value?: unknown;
}

function renderStringValue(
  _props: React.HTMLAttributes<HTMLSpanElement>,
  result: RenderResult,
  mode: "python" | "json",
): React.ReactNode {
  if (result.type !== "value" || typeof result.value !== "string") {
    return undefined;
  }
  const { value } = result;
  if (mode !== "python") {
    return renderPlainString(value);
  }

  const mimeResult = tryRenderMimeLeaf(value);
  if (mimeResult !== null) {
    return <span className="w-rjv-value">{mimeResult}</span>;
  }
  if (isUrl(value)) {
    return (
      <span className="w-rjv-value">
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-link hover:underline"
        >
          {value}
        </a>
      </span>
    );
  }
  return renderPlainString(value);
}

function renderPlainString(value: string) {
  if (value.length <= COLLAPSED_TEXT_LENGTH) {
    return undefined;
  }
  return (
    <span
      className="inline-block"
      style={{ color: "var(--w-rjv-type-string-color)" }}
    >
      &quot;
      <CollapsibleTextOutput text={value} />
      &quot;
    </span>
  );
}

function renderArrow(
  props: React.HTMLAttributes<HTMLSpanElement>,
  { keyName }: KeyRenderResult,
): React.ReactNode {
  const expanded = props.style?.transform === "rotate(0deg)";
  return (
    <button
      {...props}
      type="button"
      aria-label={`${expanded ? "Collapse" : "Expand"} ${keyName ?? "root"}`}
      aria-expanded={expanded}
    />
  );
}

const valueRender = (
  _p: Record<string, unknown>,
  r: RenderResult,
  text: string,
) =>
  r.type === "value" ? <span className="w-rjv-value">{text}</span> : undefined;

const PYTHON_TRUE_RENDER = (p: Record<string, unknown>, r: RenderResult) =>
  valueRender(p, r, "True");
const PYTHON_FALSE_RENDER = (p: Record<string, unknown>, r: RenderResult) =>
  valueRender(p, r, "False");
const PYTHON_NULL_RENDER = (p: Record<string, unknown>, r: RenderResult) =>
  valueRender(p, r, "None");
const JSON_NULL_RENDER = (p: Record<string, unknown>, r: RenderResult) =>
  valueRender(p, r, "null");

// ---------------------------------------------------------------------------
// Data truncation (pagination)
// ---------------------------------------------------------------------------

/**
 * Sentinel format: `\x00show_more\x00<remaining>|<path>`.
 * Rendered as a leaf by the library, intercepted in Row render
 * and replaced with a clickable button. Stripped from copy output.
 */
export function encodeShowMore(remaining: number, path: string): string {
  return `${SHOW_MORE}${remaining}|${path}`;
}

export function decodeShowMore(
  value: unknown,
): { remaining: string; path: string } | null {
  if (typeof value !== "string" || !value.startsWith(SHOW_MORE)) {
    return null;
  }
  const payload = value.slice(SHOW_MORE.length);
  const pipe = payload.indexOf("|");
  return { remaining: payload.slice(0, pipe), path: payload.slice(pipe + 1) };
}

/** Maps truncated container → original container for full-value copy. */
type OriginalMap = WeakMap<object, object>;

interface TruncatedResult {
  data: unknown;
  /** Lookup: truncated container → original, so copy uses full data. */
  originals: OriginalMap;
}

/**
 * Recursively cap arrays/objects at PAGE_SIZE items, appending a sentinel
 * string as the last child so the Row render can show a "show more" button.
 * Records truncated→original mapping for copy.
 */
export function truncateNode(
  node: unknown,
  limits: Record<string, number>,
  path: string,
  depth: number,
  originals: OriginalMap,
  pageSize = PAGE_SIZE,
): unknown {
  if (
    depth > 6 ||
    node === null ||
    node === undefined ||
    typeof node !== "object"
  ) {
    return node;
  }

  const limit = limits[path] ?? pageSize;

  if (Array.isArray(node)) {
    const needsTruncation = node.length > limit;
    const slice = needsTruncation ? node.slice(0, limit) : node;
    const items = slice.map((item, i) =>
      truncateNode(
        item,
        limits,
        `${path}.${i}`,
        depth + 1,
        originals,
        pageSize,
      ),
    );
    if (needsTruncation) {
      items.push(encodeShowMore(node.length - limit, path));
    }
    originals.set(items, node);
    return items;
  }

  const entries = Object.entries(node as Record<string, unknown>);
  const needsTruncation = entries.length > limit;
  const slice = needsTruncation ? entries.slice(0, limit) : entries;
  const result: Record<string, unknown> = Object.create(null);
  for (const [key, val] of slice) {
    result[key] = truncateNode(
      val,
      limits,
      `${path}.${JSON.stringify(key)}`,
      depth + 1,
      originals,
      pageSize,
    );
  }
  if (needsTruncation) {
    const sentinel = encodeShowMore(entries.length - limit, path);
    result[sentinel] = sentinel;
  }
  originals.set(result, node);
  return result;
}

function buildTruncatedData(
  data: unknown,
  limits: Record<string, number>,
  pageSize: number,
): TruncatedResult {
  const originals: OriginalMap = new WeakMap();
  const result = truncateNode(data, limits, "$", 0, originals, pageSize);
  return { data: result, originals };
}

// ---------------------------------------------------------------------------
// shouldExpandNodeInitially
// ---------------------------------------------------------------------------

/**
 * Estimate visible lines if `node` is expanded, recursively expanding
 * small children (≤ SMALL_CONTAINER entries). Large children count as
 * 1 line (collapsed). Bails at `cap` or `maxDepth`.
 */
export function estimateExpandedLines(
  node: unknown,
  cap: number,
  depth = 0,
): number {
  if (
    depth > 4 ||
    node === null ||
    node === undefined ||
    typeof node !== "object"
  ) {
    return 1;
  }
  const children: unknown[] = Array.isArray(node)
    ? node
    : Object.values(node as Record<string, unknown>);
  let lines = 0;
  for (let i = 0; i < children.length && lines < cap; i++) {
    const child = children[i];
    if (child === null || child === undefined || typeof child !== "object") {
      lines++;
    } else {
      const childLen = Array.isArray(child)
        ? child.length
        : Object.keys(child as Record<string, unknown>).length;
      lines +=
        childLen <= SMALL_CONTAINER
          ? estimateExpandedLines(child, cap - lines, depth + 1)
          : 1;
    }
  }
  return lines;
}

function shouldExpandNode(
  _isExpanded: boolean,
  { value, level }: { value?: object; level: number },
): boolean {
  if (level <= 1) {
    return true;
  }
  if (level > 5) {
    return false;
  }
  if (value === null || value === undefined || typeof value !== "object") {
    return true;
  }
  const len = Array.isArray(value) ? value.length : Object.keys(value).length;
  if (len === 0) {
    return true;
  }
  if (len > 200) {
    return false;
  }
  return estimateExpandedLines(value, 150) <= 120;
}

// ---------------------------------------------------------------------------
// Props & Component
// ---------------------------------------------------------------------------

interface Props {
  data: unknown;
  format?: "auto" | "tree" | "raw";
  /** A text label for the JSON viewer. If `false`, no label is used. */
  name?: string | false;
  className?: string;
  /** Controls value display: Python mode shows True/False/None and renders
   *  MIME-typed strings; JSON mode uses standard display. */
  valueTypes?: "json" | "python";
}

export const JsonOutput: React.FC<Props> = memo(
  ({
    data,
    format = "auto",
    name = false,
    valueTypes = "python",
    className,
  }) => {
    const { theme } = useTheme();
    if (format === "auto") {
      format = inferBestFormat(data);
    }

    const isPython = valueTypes === "python";
    const style = theme === "dark" ? marimoDarkTheme : marimoLightTheme;

    // Pagination: truncate large containers, append sentinel strings.
    const pageSize = determineMaxDisplayLength(data) ?? PAGE_SIZE;
    const [pagination, setPagination] = useState<{
      data: unknown;
      limits: Record<string, number>;
    }>({ data, limits: {} });
    if (pagination.data !== data) {
      setPagination({ data, limits: {} });
    }
    const pageLimits = pagination.limits;
    const { data: displayData, originals } = useMemo(
      () => buildTruncatedData(data, pageLimits, pageSize),
      [data, pageLimits, pageSize],
    );
    const showMore = useCallback(
      (path: string) => {
        setPagination((prev) => ({
          ...prev,
          limits: {
            ...prev.limits,
            [path]: (prev.limits[path] ?? pageSize) + pageSize,
          },
        }));
      },
      [pageSize],
    );

    const renderCopyButton = useCallback(
      (value: unknown) => {
        if (
          typeof value === "string" &&
          (value.startsWith(SHOW_MORE) ||
            (isPython &&
              (value.startsWith("text/html:") ||
                value.startsWith("image/") ||
                value.startsWith("video/"))))
        ) {
          return null;
        }
        return (
          <CopyButton value={value} isPython={isPython} originals={originals} />
        );
      },
      [isPython, originals],
    );

    const renderStringCb = useCallback(
      (props: Record<string, unknown>, result: RenderResult) =>
        renderStringValue(props, result, valueTypes),
      [valueTypes],
    );

    const renderRow = useCallback(
      (props: Record<string, unknown>, { value }: { value?: unknown }) => {
        const { children, ...rest } =
          props as React.HTMLAttributes<HTMLDivElement> & {
            children?: React.ReactNode;
          };

        const marker = decodeShowMore(value);
        if (marker) {
          return (
            <div {...rest}>
              <button
                type="button"
                className="cursor-pointer text-link hover:underline bg-transparent border-none p-0 font-inherit"
                style={{ fontSize: "inherit" }}
                onClick={(e) => {
                  e.stopPropagation();
                  showMore(marker.path);
                }}
              >
                ... {marker.remaining} more items
              </button>
            </div>
          );
        }

        return (
          <div {...rest}>
            {children}
            {renderCopyButton(value)}
          </div>
        );
      },
      [renderCopyButton, showMore],
    );

    const renderCountInfoExtra = useCallback(
      (_props: Record<string, unknown>, { value }: { value?: unknown }) =>
        renderCopyButton(value),
      [renderCopyButton],
    );

    const renderCountInfo = useCallback(
      (props: Record<string, unknown>, { value }: { value?: object }) => {
        const original = value && (originals.get(value) ?? value);
        const count = original ? Object.keys(original).length : 0;
        return (
          <span {...props}>
            {count} {count === 1 ? "Item" : "Items"}
          </span>
        );
      },
      [originals],
    );

    switch (format) {
      case "tree":
        return (
          <JsonView
            className={cn("marimo-json-output", className)}
            keyName={name || undefined}
            displayDataTypes={false}
            value={displayData as object}
            style={style}
            shortenTextAfterLength={COLLAPSED_TEXT_LENGTH}
            enableClipboard={false}
            highlightUpdates={false}
            collapsed={false}
            shouldExpandNodeInitially={shouldExpandNode}
          >
            <JsonView.String render={renderStringCb} />
            <JsonView.Colon style={{ marginRight: 4 }} />
            <JsonView.Arrow render={renderArrow} />
            <JsonView.CountInfo render={renderCountInfo} />
            {/* Render dict keys that carry Python type info (e.g. `int`, `tuple`).
                See `_key_formatter` in marimo/_output/formatters/structures.py. */}
            {isPython && <JsonView.KeyName render={renderKeyName} />}
            {isPython && <JsonView.Quote render={renderKeyQuote} />}
            {isPython && <JsonView.True render={PYTHON_TRUE_RENDER} />}
            {isPython && <JsonView.False render={PYTHON_FALSE_RENDER} />}
            <JsonView.Null
              render={isPython ? PYTHON_NULL_RENDER : JSON_NULL_RENDER}
            />
            <JsonView.Row render={renderRow} />
            <JsonView.CountInfoExtra render={renderCountInfoExtra} />
          </JsonView>
        );
      case "raw":
        return <pre className={className}>{JSON.stringify(data, null, 2)}</pre>;
      default:
        logNever(format);
        return <pre className={className}>{JSON.stringify(data, null, 2)}</pre>;
    }
  },
);
JsonOutput.displayName = "JsonOutput";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inferBestFormat(data: unknown): "tree" | "raw" {
  return typeof data === "object" && data !== null ? "tree" : "raw";
}

const REPLACE_PREFIX = "<marimo-replace>";
const REPLACE_SUFFIX = "</marimo-replace>";

/** Return `undefined` for sentinel keys/values so JSON.stringify omits them. */
export function stripSentinels(key: string, value: unknown): unknown {
  if (typeof key === "string" && key.startsWith(SHOW_MORE)) {
    return undefined;
  }
  if (typeof value === "string" && value.startsWith(SHOW_MORE)) {
    return undefined;
  }
  return value;
}

/**
 * JSON.stringify replacer that produces Python-style output:
 * - strips show-more sentinels
 * - trims mimetype prefixes from strings
 * - maps booleans to True / False
 * - maps null/undefined to None
 */
function pythonJsonReplacer(_key: string, value: unknown): unknown {
  const stripped = stripSentinels(_key, value);
  if (stripped === undefined && value !== undefined) {
    return undefined;
  }
  if (value == null) {
    return `${REPLACE_PREFIX}None${REPLACE_SUFFIX}`;
  }
  if (typeof value === "bigint") {
    return `${REPLACE_PREFIX}${value}${REPLACE_SUFFIX}`;
  }
  if (typeof value === "object" || Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string") {
    const ld = (v: string) => {
      const idx = v.indexOf(":");
      return idx === -1 ? v : v.slice(idx + 1);
    };
    // Keep float as unquoted number
    if (value.startsWith("text/plain+float:")) {
      return `${REPLACE_PREFIX}${ld(value)}${REPLACE_SUFFIX}`;
    }
    // Use BigInt to avoid precision loss
    if (value.startsWith("text/plain+bigint:")) {
      return `${REPLACE_PREFIX}${BigInt(ld(value))}${REPLACE_SUFFIX}`;
    }
    // Replace [] with () for tuples
    if (value.startsWith("text/plain+tuple:")) {
      return `${REPLACE_PREFIX}(${ld(value).slice(1, -1)})${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+set:")) {
      return `${REPLACE_PREFIX}${formatSetPayload(ld(value))}${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+frozenset:")) {
      return `${REPLACE_PREFIX}${formatFrozensetPayload(ld(value))}${REPLACE_SUFFIX}`;
    }
    if (MIME_PREFIXES.some((prefix) => value.startsWith(prefix))) {
      return ld(value);
    }
    return value;
  }
  if (typeof value === "boolean") {
    return `${REPLACE_PREFIX}${value ? "True" : "False"}${REPLACE_SUFFIX}`;
  }
  return value;
}

// Rewrite an encoded key string into the Python literal that should appear
// unquoted in the copy output. Wrapping in REPLACE_PREFIX/SUFFIX makes the
// final replace pass strip the surrounding JSON quotes.
function decodeKeyForCopy(key: string): string {
  const [data, mimeType] = splitLeaf(key);
  const wrap = (s: string) => `${REPLACE_PREFIX}${s}${REPLACE_SUFFIX}`;
  switch (`${mimeType}:`) {
    case "text/plain+int:":
      return wrap(data);
    case "text/plain+float:":
      if (data === "nan") {
        return wrap("float('nan')");
      }
      if (data === "inf") {
        return wrap("float('inf')");
      }
      if (data === "-inf") {
        return wrap("-float('inf')");
      }
      return wrap(data);
    case "text/plain+bool:":
      return wrap(data === "True" ? "True" : "False");
    case "text/plain+none:":
      return wrap("None");
    case "text/plain+tuple:":
      return wrap(formatTuplePayload(data));
    case "text/plain+frozenset:":
      return wrap(formatFrozensetPayload(data));
    case KEY_STR_PREFIX:
      // `data` is the original Python string; it stays quoted.
      return data;
    default:
      return key;
  }
}

function rewriteEncodedKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(rewriteEncodedKeys);
  }
  if (typeof value === "object" && value !== null) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) {
      const newKey = isEncodedKey(k) ? decodeKeyForCopy(k) : k;
      out[newKey] = rewriteEncodedKeys(v);
    }
    return out;
  }
  return value;
}

export function getCopyValue(value: unknown): string {
  // JSON.stringify wraps REPLACE markers in quotes;
  // strip those so None, True, False appear unquoted (Python-style).
  return JSON.stringify(rewriteEncodedKeys(value), pythonJsonReplacer, 2)
    .replaceAll(`"${REPLACE_PREFIX}`, "")
    .replaceAll(`${REPLACE_SUFFIX}"`, "");
}

/** JSON copy with sentinel stripping. */
export function jsonCopyValue(value: unknown): string {
  return JSON.stringify(value, stripSentinels, 2);
}

/**
 * Determine the max display length for a given data.
 * - For 3D arrays, we return 5
 * - For 2D arrays, return undefined <= 20 items, 10 >= 20 items, 5 >= 50 items
 * - For 1D arrays and other types, we return undefined
 */
export function determineMaxDisplayLength(data: unknown): number | undefined {
  if (!Array.isArray(data)) {
    return undefined;
  }
  const sample = data.slice(0, 15);
  let maxLength = 0;
  for (const el of sample) {
    if (Array.isArray(el)) {
      for (const next of el.slice(0, 5)) {
        if (Array.isArray(next)) {
          return 5;
        }
      }
      maxLength = Math.max(maxLength, el.length);
    }
  }
  if (maxLength <= 20) {
    return undefined;
  }
  return maxLength >= 50 ? 5 : 10;
}
