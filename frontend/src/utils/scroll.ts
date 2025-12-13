/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Scroll the element into view if it is not fully visible.
 */
export function smartScrollIntoView(
  element: HTMLElement,
  {
    offset,
    body = window,
    behavior = "smooth",
  }: {
    offset?: { top: number; bottom: number };
    body?: HTMLElement | typeof window;
    behavior?: "smooth" | "instant";
  },
) {
  const topOffset = offset?.top ?? 0;
  const bottomOffset = offset?.bottom ?? 0;
  const rect = element.getBoundingClientRect();

  if (rect.top < topOffset) {
    // Element is above the viewport, scroll to its top
    body.scrollBy({
      top: rect.top - topOffset,
      behavior,
    });
    return;
  }
  if (rect.bottom > window.innerHeight - bottomOffset) {
    // Element is below the viewport, scroll to its bottom
    body.scrollBy({
      top: rect.bottom - window.innerHeight + bottomOffset,
      behavior,
    });
    return;
  }

  // If the element is already fully in view, do nothing
}
