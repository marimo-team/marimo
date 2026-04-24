/* Copyright 2026 Marimo. All rights reserved. */

import {
  booleanType,
  type DataItemProps,
  type DataType,
  defineDataType,
  floatType,
  intType,
  JsonViewer,
  type JsonViewerKeyRenderer,
  nullType,
  objectType,
  stringType,
} from "@textea/json-viewer";
import { CheckIcon, CopyIcon } from "lucide-react";
import { memo, useState } from "react";
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

interface Props {
  /**
   * The data to display
   */
  data: unknown;

  format?: "auto" | "tree" | "raw";

  /**
   * A text label for the JSON viewer. If `false`, no label is used.
   */
  name?: string | false;

  className?: string;

  /**
   * The value types to use for the JSON viewer.
   */
  valueTypes?: "json" | "python";
}

// oxlint-disable-next-line typescript/no-explicit-any
const CopyButton: React.FC<DataItemProps<any>> = ({ value }) => {
  const skipCopy =
    typeof value === "string" &&
    (value.startsWith("text/html:") ||
      value.startsWith("image/") ||
      value.startsWith("video/"));
  const [copied, setCopied] = useState(false);

  const handleCopy = async (evt: React.MouseEvent) => {
    evt.stopPropagation();
    await copyToClipboard(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };

  if (skipCopy) {
    return null;
  }
  return (
    <button
      onClick={handleCopy}
      className={cn(
        "inline-flex ml-2 copy-button rounded w-6 h-3 justify-center items-center relative",
      )}
      aria-label="Copy to clipboard"
      type="button"
    >
      {copied ? (
        <CheckIcon className="w-5 h-5 absolute -top-0.5 p-1 hover:bg-muted rounded" />
      ) : (
        <CopyIcon className="w-5 h-5 absolute -top-0.5 p-1 hover:bg-muted rounded" />
      )}
    </button>
  );
};

// oxlint-disable-next-line typescript/no-explicit-any
const JSONCopyButton: React.FC<DataItemProps<any>> = (props) => {
  // if
  return <CopyButton {...props} value={JSON.stringify(props.value, null, 2)} />;
};

// oxlint-disable-next-line typescript/no-explicit-any
const PyCopyButton: React.FC<DataItemProps<any>> = (props) => {
  return <CopyButton {...props} value={getCopyValue(props.value)} />;
};

/**
 * Output component for JSON data.
 */
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

    const valueTypesMap: Record<string, typeof PYTHON_VALUE_TYPES> = {
      python: PYTHON_VALUE_TYPES,
      json: JSON_VALUE_TYPES,
    };

    switch (format) {
      case "tree":
        return (
          <JsonViewer
            className={cn("marimo-json-output", className)}
            rootName={name}
            theme={theme}
            displayDataTypes={false}
            value={data}
            style={{
              backgroundColor: "transparent",
            }}
            collapseStringsAfterLength={COLLAPSED_TEXT_LENGTH}
            // leave the default valueTypes as it was - 'python', only 'json' is changed
            valueTypes={valueTypesMap[valueTypes]}
            // Render dict keys that carry Python type info (e.g. `int`, `tuple`).
            // See `_key_formatter` in marimo/_output/formatters/structures.py.
            keyRenderer={valueTypes === "python" ? keyRenderer : undefined}
            // Don't group arrays, it will make the tree view look like there are nested arrays
            groupArraysAfterLength={Number.MAX_SAFE_INTEGER}
            // Built-in clipboard shifts content on hover
            // so we provide our own copy button
            enableClipboard={false}
            // Improve perf for large arrays
            maxDisplayLength={determineMaxDisplayLength(data)}
          />
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

function inferBestFormat(data: unknown): "tree" | "raw" {
  return typeof data === "object" && data !== null ? "tree" : "raw";
}

const COLLAPSED_TEXT_LENGTH = 100;
// Text with length > COLLAPSED_TEXT_LENGTH is collapsed by default, and can be expanded by clicking on it.
const CollapsibleTextOutput = (props: { text: string }) => {
  const [isCollapsed, setIsCollapsed] = useState(true);

  // Doesn't need to be collapsed
  if (props.text.length <= COLLAPSED_TEXT_LENGTH) {
    return <span className="break-all">{props.text}</span>;
  }

  if (isCollapsed) {
    return (
      <span
        className="cursor-pointer hover:opacity-90 break-all"
        onClick={() => setIsCollapsed(false)}
      >
        {props.text.slice(0, COLLAPSED_TEXT_LENGTH)}
        {props.text.length > COLLAPSED_TEXT_LENGTH && "..."}
      </span>
    );
  }

  return (
    <span
      className="cursor-pointer hover:opacity-90 break-all"
      onClick={() => setIsCollapsed(true)}
    >
      {props.text}
    </span>
  );
};

type LeafRenderer = (
  data: string,
  mimeType: OutputMessage["mimetype"],
) => React.ReactNode;

/**
 * Map from mimetype-prefix to render function.
 *
 * Render function takes leaf data as input.
 */
const LEAF_RENDERERS: Record<string, LeafRenderer> = {
  "image/": (value) => <ImageOutput src={value} />,
  "video/": (value) => <VideoOutput src={value} />,
  "text/html:": (value) => (
    <HtmlOutput html={value} inline={true} alwaysSanitizeHtml={false} />
  ),
  "text/markdown:": (value) => (
    <HtmlOutput html={value} inline={true} alwaysSanitizeHtml={true} />
  ),
  "text/plain+float:": (value) => <span>{value}</span>,
  "text/plain+bigint:": (value) => <span>{value}</span>,
  "text/plain+set:": (value) => <span>{formatSetPayload(value)}</span>,
  "text/plain+frozenset:": (value) => (
    <span>{formatFrozensetPayload(value)}</span>
  ),
  "text/plain+tuple:": (value) => <span>{value}</span>,
  "text/plain:": (value) => <CollapsibleTextOutput text={value} />,
  "application/json:": (value) => (
    <JsonOutput data={JSON.parse(value)} format="auto" />
  ),
  "application/": (value, mimeType) => {
    return (
      <OutputRenderer
        message={{
          channel: "output",
          data: value,
          mimetype: mimeType,
        }}
        // The fallback is just re-constructing the leaf and rendering it as a span
        // This could be the case where mime-type parsing is a false positive
        renderFallback={() => (
          <span>
            {mimeType}:{value}
          </span>
        )}
      />
    );
  },
};

// oxlint-disable-next-line typescript/no-explicit-any
const MIME_TYPES: DataType<any>[] = Object.entries(LEAF_RENDERERS).map(
  ([leafType, render]) => ({
    is: (value) => typeof value === "string" && value.startsWith(leafType),
    PostComponent: PyCopyButton,
    Component: (props) => renderLeaf(props.value, render),
  }),
);

const PYTHON_BOOLEAN_TYPE = defineDataType<boolean>({
  ...booleanType,
  PostComponent: PyCopyButton,
  Component: ({ value }) => <span>{value ? "True" : "False"}</span>,
});

const PYTHON_NONE_TYPE = defineDataType<null>({
  ...nullType,
  PostComponent: PyCopyButton,
  Component: () => <span>None</span>,
});

const JSON_BOOLEAN_TYPE = defineDataType<boolean>({
  ...booleanType,
  PostComponent: JSONCopyButton,
});

const JSON_NONE_TYPE = defineDataType<null>({
  ...nullType,
  PostComponent: JSONCopyButton,
  Component: () => <span>null</span>,
});

const URL_TYPE = defineDataType<string>({
  ...stringType,
  is: (value) => isUrl(value),
  PostComponent: PyCopyButton,
  Component: ({ value }) => (
    <a
      href={value}
      target="_blank"
      rel="noopener noreferrer"
      className="text-link hover:underline"
    >
      {value}
    </a>
  ),
});

const INTEGER_TYPE = defineDataType<number>({
  ...intType,
  PostComponent: JSONCopyButton,
});

const FLOAT_TYPE = defineDataType<number>({
  ...floatType,
  PostComponent: JSONCopyButton,
});

const FALLBACK_RENDERER = defineDataType<string>({
  ...stringType,
  PostComponent: PyCopyButton,
});

const OBJECT_TYPE = defineDataType<object>({
  ...objectType,
  PreComponent: (props) => (
    <>
      {objectType.PreComponent && <objectType.PreComponent {...props} />}
      <PyCopyButton {...props} />
    </>
  ),
});

const JSON_OBJECT_TYPE = defineDataType<object>({
  ...objectType,
  PreComponent: (props) => (
    <>
      {objectType.PreComponent && <objectType.PreComponent {...props} />}
      <JSONCopyButton {...props} />
    </>
  ),
});

const JSON_FALLBACK_RENDERER = defineDataType<string>({
  ...stringType,
  PostComponent: JSONCopyButton,
});

const PYTHON_VALUE_TYPES = [
  INTEGER_TYPE,
  PYTHON_BOOLEAN_TYPE,
  PYTHON_NONE_TYPE,
  ...MIME_TYPES,
  URL_TYPE,
  OBJECT_TYPE,
  FALLBACK_RENDERER,
].toReversed();
// Last one wins, so we reverse the array.

const JSON_VALUE_TYPES = [
  INTEGER_TYPE,
  FLOAT_TYPE,
  JSON_BOOLEAN_TYPE,
  JSON_NONE_TYPE,
  JSON_OBJECT_TYPE,
  JSON_FALLBACK_RENDERER,
].toReversed();

function leafData(leaf: string): string {
  return leafDataAndMimeType(leaf)[0];
}

function leafDataAndMimeType(
  leaf: string,
): [string, OutputMessage["mimetype"] | undefined] {
  const delimIndex = leaf.indexOf(":");
  if (delimIndex === -1) {
    return [leaf, undefined];
  }
  return [
    leaf.slice(delimIndex + 1),
    leaf.slice(0, delimIndex) as OutputMessage["mimetype"],
  ];
}

/**
 * Render a leaf.
 *
 * Leaf must have the format
 *
 *   <mimetype>:<data>
 *
 * where mimetype cannot contain ":".
 */
function renderLeaf(leaf: string, render: LeafRenderer): React.ReactNode {
  const [data, mimeType] = leafDataAndMimeType(leaf);
  if (mimeType) {
    return render(data, mimeType);
  }
  return <span>{leaf}</span>;
}

// Prefix marking keys that carry encoded type information from Python.
// See `_key_formatter` in marimo/_output/formatters/structures.py.
const KEY_ENCODED_PREFIX = "text/plain+";

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
// need a trailing comma — `(1)` is just `1` in Python, `(1,)` is the tuple.
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
// unquoted primitives, parens for tuple, `frozenset({...})` for frozenset,
// and the `text/plain+str:` escape re-quotes the original string.
const KEY_DECODERS: Record<string, (data: string) => React.ReactNode> = {
  "text/plain+int:": (v) => <span>{v}</span>,
  "text/plain+float:": (v) => <span>{v}</span>,
  "text/plain+bool:": (v) => <span>{v === "True" ? "True" : "False"}</span>,
  "text/plain+none:": () => <span>None</span>,
  "text/plain+tuple:": (v) => <span>{formatTuplePayload(v)}</span>,
  "text/plain+frozenset:": (v) => <span>{formatFrozensetPayload(v)}</span>,
  "text/plain+str:": (v) => <span>"{v}"</span>,
};

function isEncodedKey(key: unknown): key is string {
  return typeof key === "string" && key.startsWith(KEY_ENCODED_PREFIX);
}

// `@textea/json-viewer` drops quotes from integer-like string keys, which
// makes the string `"2"` visually identical to the decoded int `2`. Match
// the same keys the viewer strips and render them with explicit quotes.
const INT_LIKE_STRING = /^-?\d+$/;

const keyRenderer: JsonViewerKeyRenderer = Object.assign(
  ({ path }: DataItemProps) => {
    const key = path[path.length - 1];
    if (typeof key !== "string") {
      return <span>{String(key)}</span>;
    }
    if (isEncodedKey(key)) {
      const [data, mimeType] = leafDataAndMimeType(key);
      const render = KEY_DECODERS[`${mimeType}:`];
      return render ? render(data) : <span>{key}</span>;
    }
    // Plain integer-like string — quote it so it's distinct from a decoded int.
    return <span>"{key}"</span>;
  },
  {
    when: ({ path }: DataItemProps) => {
      const key = path[path.length - 1];
      return (
        isEncodedKey(key) ||
        (typeof key === "string" && INT_LIKE_STRING.test(key))
      );
    },
  },
);

const MIME_PREFIXES = Object.keys(LEAF_RENDERERS);
const REPLACE_PREFIX = "<marimo-replace>";
const REPLACE_SUFFIX = "</marimo-replace>";
/**
 * Get the string representation (as Python) of a value.
 * - recursively handles lists and dictionaries
 * - trims mimetype prefix
 * - maps booleans to True and False
 * - maps null/undefined to None
 */
function pythonJsonReplacer(_key: string, value: unknown): unknown {
  if (value == null) {
    return `${REPLACE_PREFIX}None${REPLACE_SUFFIX}`;
  }
  if (typeof value === "object") {
    return value;
  }
  if (typeof value === "bigint") {
    return `${REPLACE_PREFIX}${value}${REPLACE_SUFFIX}`;
  }
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string") {
    // If float, we want to keep the quotes around the number.
    if (value.startsWith("text/plain+float:")) {
      return `${REPLACE_PREFIX}${leafData(value)}${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+bigint:")) {
      // Use BigInt to avoid precision loss
      const number = BigInt(leafData(value));
      return `${REPLACE_PREFIX}${number}${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+tuple:")) {
      // replace first and last characters [] with ()
      return `${REPLACE_PREFIX}(${leafData(value).slice(1, -1)})${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+set:")) {
      return `${REPLACE_PREFIX}${formatSetPayload(leafData(value))}${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+frozenset:")) {
      return `${REPLACE_PREFIX}${formatFrozensetPayload(leafData(value))}${REPLACE_SUFFIX}`;
    }

    if (MIME_PREFIXES.some((prefix) => value.startsWith(prefix))) {
      return leafData(value);
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
// final regex pass strip the surrounding JSON quotes.
function decodeKeyForCopy(key: string): string {
  const [data, mimeType] = leafDataAndMimeType(key);
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
    case "text/plain+str:":
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
  // Because this results in valid json, it adds quotes around None and True/False.
  // but we want to make this look like Python, so we remove the quotes.
  return JSON.stringify(rewriteEncodedKeys(value), pythonJsonReplacer, 2)
    .replaceAll(`"${REPLACE_PREFIX}`, "")
    .replaceAll(`${REPLACE_SUFFIX}"`, "");
}

/**
 * Determine the max display length for a given data.
 * - For 3D arrays, we return 5
 * - For 2D arrays, return undefined <= 20 items, 10 >= 20 items, 5 >= 50 items
 * - For 1D arrays and other types, we return undefined
 *
 * @param data - The data to determine the max display length for.
 * @returns The max display length, or undefined to use the default.
 */
export function determineMaxDisplayLength(data: unknown): number | undefined {
  if (Array.isArray(data)) {
    const sampleElements = data.slice(0, 15);

    let maxLength = 0;
    for (const element of sampleElements) {
      if (Array.isArray(element)) {
        // Check for 3D arrays and return early
        const nextSample = element.slice(0, 5);
        for (const nextElement of nextSample) {
          if (Array.isArray(nextElement)) {
            return 5;
          }
        }

        maxLength = Math.max(maxLength, element.length);
      }
    }

    if (maxLength <= 20) {
      return undefined;
    }

    return maxLength >= 50 ? 5 : 10;
  }
}
