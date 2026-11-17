/* Copyright 2026 Marimo. All rights reserved. */

declare global {
  interface Window {
    __resizeIframe?: (iframe: HTMLIFrameElement) => void;
  }
}

// Match the inline helper in frontend/index.html, which islands do not load.
function resizeIframe(iframe: HTMLIFrameElement): void {
  const scrollbarHeight = 20;

  function setHeight() {
    const element = iframe.contentWindow?.document?.documentElement;
    if (!element || element.scrollHeight === element.clientHeight) {
      return;
    }

    const hasHorizontalScrollbar = element.scrollWidth > element.clientWidth;
    const newHeight =
      element.scrollHeight + (hasHorizontalScrollbar ? scrollbarHeight : 0);
    if (iframe.style.height !== `${newHeight}px`) {
      iframe.style.height = `${newHeight}px`;
    }
  }

  setHeight();

  const resizeObserver = new ResizeObserver(setHeight);
  const body = iframe.contentWindow?.document?.body;
  if (body) {
    resizeObserver.observe(body);
  }
}

export function registerIframeResizer(): void {
  window.__resizeIframe ??= resizeIframe;
}
