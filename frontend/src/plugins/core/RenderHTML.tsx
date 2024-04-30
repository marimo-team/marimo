/* Copyright 2024 Marimo. All rights reserved. */
import parse, { Element } from "html-react-parser";
import React from "react";

interface Options {
  html: string;
}

/**
 * We instead render HTML to React elements using html-react-parser as this keeps
 * React elements in place so React's reconciliation algorithm will update nodes instead of unmounting and remounting.
 */
export const renderHTML = ({ html }: Options) => {
  return parse(html, {
    replace: (domNode) => {
      // Don't render invalid tags
      if (
        domNode instanceof Element &&
        !/^[A-Za-z][\w-]*$/.test(domNode.name)
      ) {
        return React.createElement(React.Fragment);
      }

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
      return domNode;
    },
  });
};
