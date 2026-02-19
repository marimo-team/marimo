/* Copyright 2026 Marimo. All rights reserved. */

import parse, {
  type DOMNode,
  Element,
  type HTMLReactParserOptions,
} from "html-react-parser";
import React, {
  isValidElement,
  type JSX,
  type ReactNode,
  useMemo,
  useRef,
} from "react";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { QueryParamPreservingLink } from "@/components/ui/query-param-preserving-link";
import { DocHoverTarget } from "@/core/documentation/DocHoverTarget";
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
      return <>{children}</>; // eslint-disable-line react/jsx-no-useless-fragment
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
      return <>{children}</>; // eslint-disable-line react/jsx-no-useless-fragment
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
    // Check if script already exists
    if (!document.querySelector(`script[src="${src}"]`)) {
      const script = document.createElement("script");
      script.src = src;
      document.head.append(script);
    }
    // biome-ignore lint/complexity/noUselessFragments: this is intentional
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

  const transformFunctions: TransformFn[] = [
    addCopyButtonToCodehilite,
    preserveQueryParamsInAnchorLinks,
    wrapDocHoverTargets,
    removeWrappingBodyTags,
    removeWrappingHtmlTags,
  ];

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
      for (const transformFunction of transformFunctions) {
        const transformed = transformFunction(reactNode, domNode, index);
        if (transformed) {
          return transformed;
        }
      }
      return reactNode as JSX.Element;
    },
  });
}

export const visibleForTesting = {
  parseHtml,
};
