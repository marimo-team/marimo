/* Copyright 2024 Marimo. All rights reserved. */

import {
  booleanType,
  type DataItemProps,
  type DataType,
  defineDataType,
  floatType,
  intType,
  JsonViewer,
  nullType,
  objectType,
  stringType,
} from "@textea/json-viewer";
import { CheckIcon, CopyIcon } from "lucide-react";
import { memo, useState } from "react";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { isUrl } from "@/utils/urls";
import { useTheme } from "../../../theme/useTheme";
import { logNever } from "../../../utils/assertNever";
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const JSONCopyButton: React.FC<DataItemProps<any>> = (props) => {
  // if
  return <CopyButton {...props} value={JSON.stringify(props.value, null, 2)} />;
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
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
            // disable array grouping (it's misleading) by using a large value
            groupArraysAfterLength={1_000_000}
            // Built-in clipboard shifts content on hover
            // so we provide our own copy button
            enableClipboard={false}
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

/**
 * Map from mimetype-prefix to render function.
 *
 * Render function takes leaf data as input.
 */
const LEAF_RENDERERS = {
  "image/": (value: string) => <ImageOutput src={value} />,
  "video/": (value: string) => <VideoOutput src={value} />,
  "text/html:": (value: string) => <HtmlOutput html={value} inline={true} />,
  "text/plain+float:": (value: string) => <span>{value}</span>,
  "text/plain+set:": (value: string) => <span>set{value}</span>,
  "text/plain+tuple:": (value: string) => <span>{value}</span>,
  "text/plain:": (value: string) => <CollapsibleTextOutput text={value} />,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MIME_TYPES: Array<DataType<any>> = Object.entries(LEAF_RENDERERS).map(
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
].reverse();
// Last one wins, so we reverse the array.

const JSON_VALUE_TYPES = [
  INTEGER_TYPE,
  FLOAT_TYPE,
  JSON_BOOLEAN_TYPE,
  JSON_NONE_TYPE,
  JSON_OBJECT_TYPE,
  JSON_FALLBACK_RENDERER,
].reverse();

function leafData(leaf: string): string {
  const delimIndex = leaf.indexOf(":");
  if (delimIndex === -1) {
    return leaf;
  }
  return leaf.slice(delimIndex + 1);
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
function renderLeaf(
  leaf: string,
  render: (data: string) => React.ReactNode,
): React.ReactNode {
  if (leaf.includes(":")) {
    return render(leafData(leaf));
  }
  return <span>{leaf}</span>;
}

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
function pythonJsonReplacer(key: string, value: unknown): unknown {
  if (value == null) {
    return `${REPLACE_PREFIX}None${REPLACE_SUFFIX}`;
  }
  if (typeof value === "object") {
    return value;
  }
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string") {
    // If float, we want to keep the quotes around the number.
    if (value.startsWith("text/plain+float:")) {
      return `${REPLACE_PREFIX}${leafData(value)}${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+tuple:")) {
      // replace first and last characters [] with ()
      return `${REPLACE_PREFIX}(${leafData(value).slice(1, -1)})${REPLACE_SUFFIX}`;
    }
    if (value.startsWith("text/plain+set:")) {
      // replace first and last characters [] with {}
      return `${REPLACE_PREFIX}{${leafData(value).slice(1, -1)}}${REPLACE_SUFFIX}`;
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

export function getCopyValue(value: unknown): string {
  // Because this results in valid json, it adds quotes around None and True/False.
  // but we want to make this look like Python, so we remove the quotes.
  return JSON.stringify(value, pythonJsonReplacer, 2)
    .replaceAll(`"${REPLACE_PREFIX}`, "")
    .replaceAll(`${REPLACE_SUFFIX}"`, "");
}
