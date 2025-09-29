/* Copyright 2024 Marimo. All rights reserved. */
import parse, { type DOMNode, Element, Text } from "html-react-parser";
import type { CellId } from "@/core/cells/ids";

/**
 * Check if a DOM node matches a selector.
 */
export const matchesSelector = (domNode: Element, selector: string) => {
  const [tagName, ...classes] = selector.split(".");
  // Note domhandler.Element does not have a classList property, just an
  // (optional) string attribute.
  const classList = (domNode.attribs.class || "").split(" ");
  return (
    domNode.tagName === tagName &&
    classes.every((cls) => classList.includes(cls))
  );
};

/**
 * Check if a DOM node contains a marimo cell file.
 */
export const elementContainsMarimoCellFile = (domNode: Element) => {
  return (
    domNode &&
    matchesSelector(domNode, "span.nb") &&
    domNode.firstChild instanceof Text &&
    domNode.firstChild.nodeValue?.includes("__marimo__")
  );
};

export type TracebackInfo =
  | {
      kind: "file";
      filePath: string;
      lineNumber: number;
    }
  | {
      kind: "cell";
      cellId: CellId;
      lineNumber: number;
    };

/**
 * Extract the cell id and line number from a traceback DOM node.
 *
 * Example transformation:
 *
 *   File <span class="nb">"/tmp/marimo_<number>/__marimo__cell_<CellId>.py"</span>
 *   , line <span class="n">1</span>...
 *
 *   becomes
 *
 *   { kind: "cell", cellId: <CellID>, lineNumber: 1 }
 *
 *   or for files:
 *
 *   File <span class="nb">"/path/to/file.py"</span>
 *   , line <span class="n">42</span>...
 *
 *   becomes
 *
 *   { kind: "file", filePath: "/path/to/file.py", lineNumber: 42 }
 */
export function getTracebackInfo(domNode: DOMNode): TracebackInfo | null {
  // The traceback can be manipulated either in output render or in the pygments
  // parser. pygments extracts tokens and maps them to tags, but has no
  // inherent knowledge of the traceback structure, so the methodology would
  // have to be similar. Moreover, the client side "cell-id" is particular to
  // frontend, so frontend handling would have to occur anyway.
  //
  // A little verbose working with intermediate representation, but best reference
  // for documentation is found in library source (@domhandler/src/node.ts)
  //
  // Expected to transform:
  //
  // File <span class="nb">"/tmp/marimo_<number>/__marimo__cell_<cell-id>.py</span>
  // , line <span class="n">1</span>...
  //
  // into
  //
  // File marimo://notebook#cell=<CellID>, line 1, in <module>
  if (
    domNode instanceof Element &&
    domNode.firstChild instanceof Text &&
    matchesSelector(domNode, "span.nb")
  ) {
    const nextSibling = domNode.next;
    if (nextSibling && nextSibling instanceof Text) {
      const lineSibling = nextSibling.next;
      if (
        lineSibling &&
        lineSibling instanceof Element &&
        lineSibling.firstChild instanceof Text &&
        matchesSelector(lineSibling, "span.m")
      ) {
        const lineNumber = Number.parseInt(
          lineSibling.firstChild.nodeValue || "0",
          10,
        );
        if (domNode.firstChild.nodeValue?.includes("__marimo__")) {
          const cellId = /__marimo__cell_(\w+)_/.exec(
            domNode.firstChild.nodeValue,
          )?.[1] as CellId;
          if (cellId && lineNumber) {
            return { kind: "cell", cellId, lineNumber };
          }
        } else {
          const filePath = /"(.+?)"/.exec(domNode.firstChild.nodeValue)?.[1];
          if (filePath && lineNumber) {
            return { kind: "file", filePath, lineNumber };
          }
        }
      }
    }
  }
  return null;
}

export function extractAllTracebackInfo(traceback: string): TracebackInfo[] {
  const infos: TracebackInfo[] = [];

  // Parse the traceback to recurse over the DOM.
  // We don't do anything with the result.
  parse(traceback, {
    replace: (domNode) => {
      const info = getTracebackInfo(domNode);
      if (info) {
        infos.push(info);
        return "dummy";
      }
    },
  });
  return infos;
}
