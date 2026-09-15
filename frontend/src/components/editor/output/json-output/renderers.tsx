/* Copyright 2026 Marimo. All rights reserved. */
import { useState } from "react";
import type { OutputMessage } from "@/core/kernel/messages";
import { isUrl } from "@/utils/urls";
import { OutputRenderer } from "../../Output";
import { HtmlOutput } from "../HtmlOutput";
import { ImageOutput } from "../ImageOutput";
import { JsonOutput } from "../JsonOutput";
import { VideoOutput } from "../VideoOutput";
import {
  decodePythonKey,
  formatTuplePayload,
  formatSetPayload,
  formatFrozensetPayload,
  splitLeaf,
} from "./formatting";

export const COLLAPSED_TEXT_LENGTH = 100;

// Keep long text and quotes wrapping together.
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
  "text/plain+tuple:": (v) => <span>{formatTuplePayload(v)}</span>,
  "text/plain:": (v) => <CollapsibleTextOutput text={v} />,
  "application/json:": (v) => <JsonOutput data={JSON.parse(v)} />,
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

function tryRenderMimeLeaf(value: string): React.ReactNode | null {
  for (const prefix of Object.keys(LEAF_RENDERERS)) {
    if (value.startsWith(prefix)) {
      const [data, mime] = splitLeaf(value);
      return mime
        ? LEAF_RENDERERS[prefix](data, mime as OutputMessage["mimetype"])
        : null;
    }
  }
  return null;
}

interface KeyRenderResult {
  keyName?: string | number;
}

export function renderKeyName(
  props: Record<string, unknown>,
  { keyName }: KeyRenderResult,
): React.ReactNode {
  const decoded = decodePythonKey(keyName);
  if (!decoded) {
    return undefined;
  }
  return <span {...props}>{decoded.text}</span>;
}

export function renderKeyQuote(
  _props: Record<string, unknown>,
  { keyName }: KeyRenderResult,
): React.ReactNode {
  // The viewer treats null/undefined as a request for its default quotes.
  return decodePythonKey(keyName)?.quoted === false ? <span /> : undefined;
}

export interface RenderResult {
  type: string;
  value?: unknown;
}

export function renderStringValue(
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

export function renderArrow(
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

function renderLiteral(text: string) {
  return (_props: Record<string, unknown>, { type }: RenderResult) =>
    type === "value" ? <span className="w-rjv-value">{text}</span> : undefined;
}

export const PYTHON_TRUE_RENDER = renderLiteral("True");
export const PYTHON_FALSE_RENDER = renderLiteral("False");
export const PYTHON_NULL_RENDER = renderLiteral("None");
export const JSON_NULL_RENDER = renderLiteral("null");
