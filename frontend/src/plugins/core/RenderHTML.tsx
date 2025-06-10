/* Copyright 2024 Marimo. All rights reserved. */
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import parse, {
  Element,
  type HTMLReactParserOptions,
  type DOMNode,
} from "html-react-parser";
import React, { useId, type ReactNode, type JSX } from "react";

type ReplacementFn = NonNullable<HTMLReactParserOptions["replace"]>;
type TransformFn = NonNullable<HTMLReactParserOptions["transform"]>;

interface Options {
  html: string;
  additionalReplacements?: ReplacementFn[];
}

const replaceValidTags = (domNode: DOMNode) => {
  // Don't render invalid tags
  if (domNode instanceof Element && !/^[A-Za-z][\w-]*$/.test(domNode.name)) {
    return React.createElement(React.Fragment);
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
    // eslint-disable-next-line react/jsx-no-useless-fragment
    return <></>;
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

const CopyableCode = ({ children }: { children: ReactNode }) => {
  const id = useId();
  return (
    <div className="relative group codehilite-wrapper" id={id}>
      {children}

      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <CopyClipboardIcon
          tooltip={false}
          className="p-1"
          value={() => {
            const codeElement = document.getElementById(id)?.firstChild;
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

export const renderHTML = ({ html, additionalReplacements = [] }: Options) => {
  const renderFunctions: ReplacementFn[] = [
    replaceValidTags,
    replaceValidIframes,
    replaceSrcScripts,
    ...additionalReplacements,
  ];

  const transformFunctions: TransformFn[] = [addCopyButtonToCodehilite];

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
      // eslint-disable-next-line react/jsx-no-useless-fragment
      return reactNode as JSX.Element;
    },
  });
};
