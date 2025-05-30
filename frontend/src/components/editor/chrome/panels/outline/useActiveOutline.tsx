/* Copyright 2024 Marimo. All rights reserved. */
import type { OutlineItem } from "@/core/cells/outline";
import { headingToIdentifier } from "@/core/dom/outline";
import { getInitialAppMode } from "@/core/mode";
import { Logger } from "@/utils/Logger";
import { useEffect, useRef, useState } from "react";

function getRootScrollableElement() {
  // HACK: this is a bit leaky
  // this gets the root element that contains the scrollable content
  return getInitialAppMode() === "edit"
    ? document.getElementById("App")
    : undefined;
}

/**
 * React hook to find the active header in the outline
 */
export function useActiveOutline(
  headerElements: Array<readonly [HTMLElement, string]>,
) {
  const [activeHeaderId, setActiveHeaderId] = useState<string | undefined>(
    undefined,
  );
  const observerRef = useRef<IntersectionObserver | null>(null);
  const topmostHeader = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (headerElements.length === 0) {
      return;
    }

    const callback: IntersectionObserverCallback = (entries) => {
      let needsUpdate = false;

      entries.forEach((entry) => {
        const element = entry.target as HTMLElement;
        if (entry.isIntersecting) {
          if (
            !topmostHeader.current ||
            element.getBoundingClientRect().top <
              topmostHeader.current.getBoundingClientRect().top
          ) {
            topmostHeader.current = element;
            needsUpdate = true;
          }
        } else if (element === topmostHeader.current) {
          topmostHeader.current = null;
          needsUpdate = true;
        }
      });

      if (needsUpdate && topmostHeader.current) {
        const identifier = headingToIdentifier(topmostHeader.current);
        const id = "id" in identifier ? identifier.id : identifier.path;
        setActiveHeaderId(id);
      }
    };

    observerRef.current = new IntersectionObserver(callback, {
      root: getRootScrollableElement(),
      rootMargin: "0px",
      threshold: 0,
    });

    headerElements.forEach((element) => {
      if (element) {
        observerRef.current?.observe(element[0]);
      }
    });

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
      topmostHeader.current = null;
    };
  }, [headerElements]);

  return { activeHeaderId };
}

/**
 * Finds all the outline elements in the document
 */
export function findOutlineElements(items: OutlineItem[]) {
  if (items.length === 0) {
    return [];
  }

  // Map of selector to its occurrences
  const seen = new Map<string, number>();

  return items
    .map((item) => {
      const identifier = "id" in item.by ? item.by.id : item.by.path;
      // Keep track of how many times we've seen this selector
      const occurrences = seen.get(identifier) ?? 0;
      seen.set(identifier, occurrences + 1);

      const el = findOutlineItem(item, occurrences);
      if (!el) {
        return null;
      }

      return [el, identifier] as const;
    })
    .filter(Boolean);
}

/**
 * Scrolls to the outline item in the document
 */
export function scrollToOutlineItem(item: OutlineItem, index: number) {
  const element = findOutlineItem(item, index);
  if (!element) {
    Logger.warn("Could not find element for outline item", item);
    return;
  }

  element.scrollIntoView({ behavior: "smooth", block: "start" });

  // Add underline to the element for a few seconds
  element.classList.add("outline-item-highlight");
  setTimeout(() => {
    element.classList.remove("outline-item-highlight");
  }, 3000);
}

/**
 * Finds the element in the document that matches the outline item
 */
export function findOutlineItem(
  item: OutlineItem,
  index: number,
): HTMLElement | null {
  if ("id" in item.by) {
    // Selectors may be duplicated, so we need to use querySelectorAll
    // IDs that start with a number are invalid, so we need to escape them
    const elems = document.querySelectorAll<HTMLElement>(
      `[id="${CSS.escape(item.by.id)}"]`,
    );
    return elems[index];
  }
  const el = document.evaluate(
    item.by.path,
    document,
    null,
    XPathResult.FIRST_ORDERED_NODE_TYPE,
    null,
  ).singleNodeValue as HTMLElement;
  return el;
}
