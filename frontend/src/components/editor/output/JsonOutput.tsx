/* Copyright 2024 Marimo. All rights reserved. */
import { memo, useState } from "react";
import {
  type DataType,
  JsonViewer,
  booleanType,
  defineDataType,
  nullType,
  stringType,
} from "@textea/json-viewer";

import { HtmlOutput } from "./HtmlOutput";
import { ImageOutput } from "./ImageOutput";
import { TextOutput } from "./TextOutput";
import { VideoOutput } from "./VideoOutput";
import { logNever } from "../../../utils/assertNever";
import { useTheme } from "../../../theme/useTheme";
import { isUrl } from "@/utils/urls";
import { copyToClipboard } from "@/utils/copy";

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
}

/**
 * Output component for JSON data.
 */
export const JsonOutput: React.FC<Props> = memo(
  ({ data, format = "auto", name = false, className }) => {
    const { theme } = useTheme();
    if (format === "auto") {
      format = inferBestFormat(data);
    }

    switch (format) {
      case "tree":
        return (
          <JsonViewer
            className="marimo-json-output"
            rootName={name}
            theme={theme}
            displayDataTypes={false}
            value={data}
            style={{
              backgroundColor: "transparent",
            }}
            collapseStringsAfterLength={COLLAPSED_TEXT_LENGTH}
            valueTypes={VALUE_TYPE}
            // disable array grouping (it's misleading) by using a large value
            groupArraysAfterLength={1_000_000}
            onCopy={async (_path, value) => {
              await copyToClipboard(getCopyValue(value));
              return value;
            }}
            enableClipboard={true}
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
    return <span>{props.text}</span>;
  }

  if (isCollapsed) {
    return (
      <span
        className="cursor-pointer hover:opacity-90"
        onClick={() => setIsCollapsed(false)}
      >
        {props.text.slice(0, COLLAPSED_TEXT_LENGTH)}
        {props.text.length > COLLAPSED_TEXT_LENGTH && "..."}
      </span>
    );
  }

  return (
    <span
      className="cursor-pointer hover:opacity-90"
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
    Component: (props) => renderLeaf(props.value, render),
  }),
);

const PYTHON_BOOLEAN_TYPE = defineDataType<boolean>({
  ...booleanType,
  Component: ({ value }) => <span>{value ? "True" : "False"}</span>,
});

const PYTHON_NONE_TYPE = defineDataType<null>({
  ...nullType,
  Component: () => <span>None</span>,
});

const URL_TYPE = defineDataType<string>({
  ...stringType,
  is: (value) => isUrl(value),
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

const VALUE_TYPE = [
  ...MIME_TYPES,
  PYTHON_BOOLEAN_TYPE,
  PYTHON_NONE_TYPE,
  URL_TYPE,
];

function leafData(leaf: string): string {
  const delimIndex = leaf.indexOf(":");
  if (delimIndex === -1) {
    throw new Error("Invalid leaf");
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
  render: (data: string) => JSX.Element,
): JSX.Element {
  try {
    return render(leafData(leaf));
  } catch {
    return <TextOutput text={`Invalid leaf: ${leaf}`} />;
  }
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
  return JSON.stringify(value, pythonJsonReplacer)
    .replaceAll(`"${REPLACE_PREFIX}`, "")
    .replaceAll(`${REPLACE_SUFFIX}"`, "");
}
