/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Scroll the element into view if it is not fully visible.
 */
export function smartScrollIntoView(
  element: HTMLElement,
  offset?: { top: number; bottom: number },
  body: HTMLElement | typeof window = window,
) {
  const topOffset = offset?.top ?? 0;
  const bottomOffset = offset?.bottom ?? 0;
  const rect = element.getBoundingClientRect();

  if (rect.top < topOffset) {
    // Element is above the viewport, scroll to its top
    body.scrollBy({
      top: rect.top - topOffset,
      behavior: "smooth",
    });
    return;
  } else if (rect.bottom > window.innerHeight - bottomOffset) {
    // Element is below the viewport, scroll to its bottom
    body.scrollBy({
      top: rect.bottom - window.innerHeight + bottomOffset,
      behavior: "smooth",
    });
    return;
  }

  // If the element is already fully in view, do nothing
}
