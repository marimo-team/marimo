import { useCallback, useRef } from "react";
import { serializeBlob } from "@/utils/blob";

type Base64ImageString = string & { readonly __base64: unique symbol };

function createBase64String(value: string): Base64ImageString {
  return value as Base64ImageString;
}

async function hashBase64(data: string): Promise<string> {
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);
  const hashBuffer = await crypto.subtle.digest("SHA-256", dataBuffer);
  const hashArray = [...new Uint8Array(hashBuffer)];
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function fetchImageAsBase64(url: string): Promise<string> {
  const response = await fetch(url);
  const blob = await response.blob();
  const dataUrl = await serializeBlob(blob);
  const base64 = dataUrl.split(",")[1];
  return base64 ?? "";
}

function querySelectorAllDeep(selector: string): Element[] {
  const results: Element[] = [];
  const visited = new Set<Node>();

  function search(node: Node): void {
    if (visited.has(node)) return;
    visited.add(node);

    if (node.nodeType !== Node.ELEMENT_NODE) return;

    const el = node as Element;

    try {
      if (el.matches(selector)) {
        results.push(el);
      }
    } catch {
      // Ignore invalid selectors
    }

    for (const child of el.children) {
      search(child);
    }

    if (el.shadowRoot?.children) {
      for (const child of el.shadowRoot.children) {
        search(child);
      }
    }
  }

  search(document.documentElement);
  return results;
}

interface Candidate {
  selector: string;
  element: HTMLImageElement | HTMLCanvasElement | SVGElement;
  rect: DOMRect;
  isHidden: boolean;
}

function isInViewport(rect: DOMRect): boolean {
  return (
    rect.width > 0 &&
    rect.height > 0 &&
    rect.top < window.innerHeight &&
    rect.left < window.innerWidth &&
    rect.bottom > 0 &&
    rect.right > 0
  );
}

export function useCaptureNotebookPreview() {
  const lastHashRef = useRef<string | null>(null);

  const capturePreviewInternal =
    useCallback(async (): Promise<Base64ImageString | null> => {
      const selectors = [
        // TODO(jabolo): Add more selectors as needed for major plotting libraries
        "svg.main-svg", // plotly
        'img[src^="data:image"]',
        'img[src^="blob:"]',
        "img",
        "canvas",
      ];

      const candidates: Candidate[] = [];

      for (const selector of selectors) {
        const elements = querySelectorAllDeep(selector);
        for (const element of elements) {
          if (
            !(
              element instanceof HTMLImageElement ||
              element instanceof HTMLCanvasElement ||
              element instanceof SVGElement
            )
          ) {
            continue;
          }

          const computedStyle = window.getComputedStyle(element);
          const isHidden =
            computedStyle.display === "none" ||
            computedStyle.visibility === "hidden";

          candidates.push({
            selector,
            element,
            rect: element.getBoundingClientRect(),
            isHidden,
          });
        }
      }

      const visibleCandidate = candidates.find(
        (c) => !c.isHidden && isInViewport(c.rect),
      );
      if (!visibleCandidate) return null;

      const { element: targetElement } = visibleCandidate;

      if (targetElement instanceof HTMLImageElement) {
        return captureImageElement(targetElement);
      }
      if (targetElement instanceof HTMLCanvasElement) {
        return captureCanvasElement(targetElement);
      }
      if (targetElement instanceof SVGElement) {
        return captureSvgElement(targetElement);
      }

      return null;
    }, []);

  return useCallback(async (): Promise<Base64ImageString | null> => {
    const preview = await capturePreviewInternal();
    if (!preview) return null;

    const hash = await hashBase64(preview);
    if (hash === lastHashRef.current) return null;

    lastHashRef.current = hash;
    return preview;
  }, [capturePreviewInternal]);
}

async function captureImageElement(
  img: HTMLImageElement,
): Promise<Base64ImageString | null> {
  const src = img.src;

  if (src.startsWith("data:")) {
    return createBase64String(src);
  }

  try {
    const base64 = await fetchImageAsBase64(src);
    return createBase64String(`data:image/png;base64,${base64}`);
  } catch {
    return null;
  }
}

async function captureCanvasElement(
  canvas: HTMLCanvasElement,
): Promise<Base64ImageString> {
  const dataUrl = canvas.toDataURL("image/png");
  return createBase64String(dataUrl);
}

async function captureSvgElement(
  svg: SVGElement,
): Promise<Base64ImageString | null> {
  try {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    const rect = svg.getBoundingClientRect();
    canvas.width = Math.ceil(rect.width);
    canvas.height = Math.ceil(rect.height);

    const svgString = new XMLSerializer().serializeToString(svg);
    const url = URL.createObjectURL(
      new Blob([svgString], { type: "image/svg+xml" }),
    );

    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = reject;
      img.src = url;
    });

    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);

    const dataUrl = canvas.toDataURL("image/png");
    return createBase64String(dataUrl);
  } catch {
    return null;
  }
}
