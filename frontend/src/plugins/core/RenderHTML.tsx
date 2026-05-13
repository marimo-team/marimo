/* Copyright 2026 Marimo. All rights reserved. */

import parse, {
  type DOMNode,
  Element,
  type HTMLReactParserOptions,
} from "html-react-parser";
import React, {
  cloneElement,
  isValidElement,
  type JSX,
  type ReactNode,
  useMemo,
  useRef,
} from "react";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { QueryParamPreservingLink } from "@/components/ui/query-param-preserving-link";
import { Tooltip } from "@/components/ui/tooltip";
import { DocHoverTarget } from "@/core/documentation/DocHoverTarget";
import { hasTrustedNotebookContext } from "@/core/static/export-context";
import { Logger } from "@/utils/Logger";
import { sanitizeHtml, useSanitizeHtml } from "./sanitize";

type ReplacementFn = NonNullable<HTMLReactParserOptions["replace"]>;
type TransformFn = NonNullable<HTMLReactParserOptions["transform"]>;

interface Options {
  html: string;
  /**
   * Whether to sanitize the HTML.
   * @default true
   */
  alwaysSanitizeHtml?: boolean;
  additionalReplacements?: ReplacementFn[];
}

const replaceValidTags = (domNode: DOMNode) => {
  // Don't render invalid tags
  if (domNode instanceof Element && !/^[A-Za-z][\w-]*$/.test(domNode.name)) {
    return React.createElement(React.Fragment);
  }
};

const removeWrappingBodyTags: TransformFn = (
  reactNode: ReactNode,
  domNode: DOMNode,
) => {
  // Remove body tags and just render their children
  if (domNode instanceof Element && domNode.name === "body") {
    if (isValidElement(reactNode) && "props" in reactNode) {
      const props = reactNode.props as { children?: ReactNode };
      const children = props.children;
      return <>{children}</>; // oxlint-disable-line react/jsx-no-useless-fragment
    }
    return;
  }
};

const removeWrappingHtmlTags: TransformFn = (
  reactNode: ReactNode,
  domNode: DOMNode,
) => {
  // Remove html tags and just render their children
  if (domNode instanceof Element && domNode.name === "html") {
    if (isValidElement(reactNode) && "props" in reactNode) {
      const props = reactNode.props as { children?: ReactNode };
      const children = props.children;
      return <>{children}</>; // oxlint-disable-line react/jsx-no-useless-fragment
    }
    return;
  }
};

const replaceValidIframes = (domNode: DOMNode) => {
  // For iframe, we just want to use dangerouslySetInnerHTML so:
  // 1) we can remount the iframe when the src changes
  // 2) keep event attributes (onload, etc.) since this library removes them
  if (
    domNode instanceof Element &&
    domNode.attribs &&
    domNode.name === "iframe"
  ) {
    const element = document.createElement("iframe");
    Object.entries(domNode.attribs).forEach(([key, value]) => {
      // If it is wrapped in quotes, remove them
      // html-react-parser will return quoted keys if they are
      // valueless attributes (e.g. "allowfullscreen")
      if (key.startsWith('"') && key.endsWith('"')) {
        key = key.slice(1, -1);
      }
      element.setAttribute(key, value);
    });
    return <div dangerouslySetInnerHTML={{ __html: element.outerHTML }} />;
  }
};

const replaceSrcScripts = (domNode: DOMNode): JSX.Element | undefined => {
  if (domNode instanceof Element && domNode.name === "script") {
    // Missing src, we don't handle inline scripts
    const src = domNode.attribs.src;
    if (!src) {
      return;
    }
    // Only append notebook-authored scripts when the page is a trusted
    // context (the user has run a cell, the page is a trusted export, or
    // we're running in read/app mode). In untrusted edit mode before any
    // user interaction, drop the script and log a warning. Outer
    // sanitization will normally strip <script> tags already; this is
    // defense-in-depth for flows that reparse children with
    // alwaysSanitizeHtml: false (see registerReactComponent.getChildren).
    if (!hasTrustedNotebookContext()) {
      Logger.warn(
        `[RenderHTML] refusing <script src> in untrusted context: ${src}`,
      );
      // oxlint-disable-next-line react/jsx-no-useless-fragment
      return <></>;
    }
    // Check if script already exists. Avoid building a CSS selector from
    // notebook-provided input, which can throw for valid URLs containing
    // selector-significant characters (e.g. IPv6 hosts with `[`/`]`).
    const scriptExists = [...document.querySelectorAll("script[src]")].some(
      (existingScript) => existingScript.getAttribute("src") === src,
    );
    if (!scriptExists) {
      const script = document.createElement("script");
      script.src = src;
      document.head.append(script);
    }
    // oxlint-disable-next-line react/jsx-no-useless-fragment
    return <></>;
  }
};

const preserveQueryParamsInAnchorLinks: TransformFn = (
  reactNode: ReactNode,
  domNode: DOMNode,
): JSX.Element | undefined => {
  if (domNode instanceof Element && domNode.name === "a") {
    const href = domNode.attribs.href;
    // Only handle anchor links (starting with #)
    if (href?.startsWith("#") && !href.startsWith("#code/")) {
      // Get the children from the parsed React node
      let children: ReactNode = null;
      if (isValidElement(reactNode) && "props" in reactNode) {
        const props = reactNode.props as { children?: ReactNode };
        children = props.children;
      }

      return (
        <QueryParamPreservingLink href={href} {...domNode.attribs}>
          {children}
        </QueryParamPreservingLink>
      );
    }
  }
};

// Add copy button to codehilite blocks
const addCopyButtonToCodehilite: TransformFn = (
  reactNode: ReactNode,
  domNode: DOMNode,
  index: number,
): JSX.Element | undefined => {
  if (
    domNode instanceof Element &&
    domNode.name === "div" &&
    domNode.attribs?.class?.includes("codehilite")
  ) {
    return <CopyableCode key={index}>{reactNode}</CopyableCode>;
  }
};

// Decorator (not a match-and-replace transform): applies a src-based key
// to <img> elements so they remount on src change. Reusing an <img> across
// src changes can leave the previous image painted (e.g. when the new
// request is slow/blocked, served stale by a CDN, or fails CORS), so the
// user sees the old image even though the HTML source is up to date.
//
// Runs unconditionally after the match-and-replace transforms so it still
// applies when an <img> was already wrapped by, say, wrapTooltipTargets.
const keyImagesBySrc: TransformFn = (
  reactNode: ReactNode,
  domNode: DOMNode,
  index: number,
): JSX.Element | undefined => {
  if (!(domNode instanceof Element) || domNode.name !== "img") {
    return undefined;
  }
  const src = domNode.attribs?.src;
  if (!src || !isValidElement(reactNode)) {
    return undefined;
  }
  // data: URIs are inline — no network fetch — so they can't go stale.
  // Skip to avoid bloating the React key with a megabyte base64 payload.
  // URI schemes are case-insensitive per RFC 3986.
  if (/^data:/i.test(src)) {
    return undefined;
  }
  return cloneElement(reactNode, { key: `${src}-${index}` });
};

// Wrap elements with data-marimo-doc attribute in a DocHoverTarget
const wrapDocHoverTargets: TransformFn = (
  reactNode: ReactNode,
  domNode: DOMNode,
): JSX.Element | undefined => {
  if (domNode instanceof Element && domNode.attribs?.["data-marimo-doc"]) {
    const qualifiedName = domNode.attribs["data-marimo-doc"];
    return (
      <DocHoverTarget qualifiedName={qualifiedName}>{reactNode}</DocHoverTarget>
    );
  }
};

// Wrap elements with data-tooltip attribute in a Tooltip component.
// This renders the tooltip in a portal (top layer), fixing clipping inside
// containers with overflow:hidden (e.g. grid cells).
//
// Marimo custom elements (marimo-button, etc.) are skipped — they handle
// tooltips via the plugin system inside their Shadow DOM. Wrapping them here
// would create a duplicate tooltip with incorrect positioning and
// un-decoded JSON content (the data-* value is JSON-encoded by the backend).
const wrapTooltipTargets: TransformFn = (
  reactNode: ReactNode,
  domNode: DOMNode,
): JSX.Element | undefined => {
  if (domNode instanceof Element && domNode.attribs?.["data-tooltip"]) {
    const tagName = domNode.name?.toLowerCase() ?? "";
    if (tagName.startsWith("marimo-")) {
      return undefined;
    }
    const tooltipContent = domNode.attribs["data-tooltip"];
    return (
      <Tooltip content={tooltipContent}>{reactNode as JSX.Element}</Tooltip>
    );
  }
};

const CopyableCode = ({ children }: { children: ReactNode }) => {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div className="relative group codehilite-wrapper" ref={ref}>
      {children}

      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <CopyClipboardIcon
          tooltip={false}
          className="p-1"
          value={() => {
            const codeElement = ref.current?.firstChild;
            if (codeElement) {
              return codeElement.textContent || "";
            }
            return "";
          }}
        />
      </div>
    </div>
  );
};

/**
 *
 * @param html - The HTML to render.
 * @param additionalReplacements - Additional replacements to apply to the HTML.
 * @param alwaysSanitizeHtml - Whether to sanitize the HTML.
 * @returns
 */
export const renderHTML = ({
  html,
  additionalReplacements = [],
  alwaysSanitizeHtml = true,
}: Options) => {
  return (
    <RenderHTML
      html={html}
      alwaysSanitizeHtml={alwaysSanitizeHtml}
      additionalReplacements={additionalReplacements}
    />
  );
};

const RenderHTML = ({
  html,
  additionalReplacements = [],
  alwaysSanitizeHtml,
}: Options) => {
  const shouldSanitizeHtml = useSanitizeHtml();

  const sanitizedHtml = useMemo(() => {
    if (alwaysSanitizeHtml || shouldSanitizeHtml) {
      return sanitizeHtml(html);
    }
    return html;
  }, [html, alwaysSanitizeHtml, shouldSanitizeHtml]);

  return parseHtml({
    html: sanitizedHtml,
    additionalReplacements,
  });
};

function parseHtml({
  html,
  additionalReplacements = [],
}: Pick<Options, "html" | "additionalReplacements">) {
  const renderFunctions: ReplacementFn[] = [
    replaceValidTags,
    replaceValidIframes,
    replaceSrcScripts,
    ...additionalReplacements,
  ];

  // Match-and-replace transforms: the first one that returns a value wins
  // (short-circuits the rest).
  const transformFunctions: TransformFn[] = [
    addCopyButtonToCodehilite,
    preserveQueryParamsInAnchorLinks,
    wrapDocHoverTargets,
    wrapTooltipTargets,
    removeWrappingBodyTags,
    removeWrappingHtmlTags,
  ];

  // Decorators: run unconditionally on the result of the transform pipeline
  // and may further wrap/clone it. Used for cross-cutting concerns that
  // should apply regardless of which (if any) match-and-replace transform
  // ran above.
  const decoratorFunctions: TransformFn[] = [keyImagesBySrc];

  return parse(html, {
    replace: (domNode: DOMNode, index: number) => {
      for (const renderFunction of renderFunctions) {
        const replacement = renderFunction(domNode, index);
        if (replacement) {
          return replacement;
        }
      }
      return domNode;
    },
    transform: (reactNode: ReactNode, domNode: DOMNode, index: number) => {
      let result: ReactNode = reactNode as JSX.Element;
      for (const transformFunction of transformFunctions) {
        const transformed = transformFunction(result, domNode, index);
        if (transformed) {
          result = transformed;
          break;
        }
      }
      for (const decorate of decoratorFunctions) {
        const decorated = decorate(result, domNode, index);
        if (decorated) {
          result = decorated;
        }
      }
      return result as JSX.Element;
    },
  });
}

export const visibleForTesting = {
  parseHtml,
};
