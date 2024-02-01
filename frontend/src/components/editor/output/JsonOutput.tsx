/* Copyright 2024 Marimo. All rights reserved. */
import { memo } from "react";
import { DataType, JsonViewer } from "@textea/json-viewer";

import { HtmlOutput } from "./HtmlOutput";
import { ImageOutput } from "./ImageOutput";
import { TextOutput } from "./TextOutput";
import { VideoOutput } from "./VideoOutput";
import { logNever } from "../../../utils/assertNever";
import { useThemeForPlugin } from "../../../theme/useTheme";

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
    const { theme } = useThemeForPlugin();
    if (format === "auto") {
      format = inferBestFormat(data);
    }

    switch (format) {
      case "tree":
        return (
          <JsonViewer
            className={"marimo-json-output"}
            rootName={name}
            theme={theme}
            value={data}
            style={{
              backgroundColor: "transparent",
            }}
            valueTypes={VALUE_TYPE}
            // disable array grouping (it's misleading) by using a large value
            groupArraysAfterLength={1_000_000}
            // TODO(akshayka): disable clipboard until we have a better
            // solution: copies raw values, shifts content; can use onCopy prop
            // to override what is copied to clipboard
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

/**
 * Map from mimetype-prefix to render function.
 *
 * Render function takes leaf data as input.
 */
const LEAF_RENDERERS = {
  "image/": (value: string) => <ImageOutput src={value} />,
  "video/": (value: string) => <VideoOutput src={value} />,
  "text/html": (value: string) => <HtmlOutput html={value} inline={true} />,
  "text/plain": (value: string) => <TextOutput text={value} />,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const VALUE_TYPE: Array<DataType<any>> = Object.entries(LEAF_RENDERERS).map(
  ([leafType, render]) => ({
    is: (value) => typeof value === "string" && value.startsWith(leafType),
    Component: (props) => renderLeaf(props.value, render),
  }),
);

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
    return <TextOutput text={`Invalid leaf: {leaf}`} />;
  }
}
