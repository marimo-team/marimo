/* Copyright 2024 Marimo. All rights reserved. */
/*
 * Simplified version of useResizeObserver from https://usehooks-ts.com/react-hook/use-resize-observer
 * Use this when you want to attach a resize observer conditionally using the `skip` option.
 */

import { useEffect, useRef } from "react";

import type { RefObject } from "react";

interface Size {
  width: number | undefined;
  height: number | undefined;
}

interface UseResizeObserverOptions<T extends HTMLElement = HTMLElement> {
  ref: RefObject<T | null>;
  skip?: boolean;
  onResize?: (size: Size) => void;
  box?: "border-box" | "content-box" | "device-pixel-content-box";
}

const initialSize: Size = {
  width: undefined,
  height: undefined,
};

export function useResizeObserver<T extends HTMLElement = HTMLElement>(
  options: UseResizeObserverOptions<T>,
): void {
  const { ref, box = "content-box", skip } = options;
  // eslint-disable-next-line react/hook-use-state
  const previousSize = useRef<Size>({ ...initialSize });
  const onResize = useRef<((size: Size) => void) | undefined>(undefined);
  // eslint-disable-next-line react-hooks/react-compiler
  onResize.current = options.onResize;

  useEffect(() => {
    if (!ref.current || skip) {
      return;
    }

    if (typeof window === "undefined" || !("ResizeObserver" in window)) {
      return;
    }

    const observer = new ResizeObserver(([entry]) => {
      const boxProp =
        box === "border-box"
          ? "borderBoxSize"
          : box === "device-pixel-content-box"
            ? "devicePixelContentBoxSize"
            : "contentBoxSize";

      const newWidth = extractSize(entry, boxProp, "inlineSize");
      const newHeight = extractSize(entry, boxProp, "blockSize");

      const hasChanged =
        previousSize.current.width !== newWidth ||
        previousSize.current.height !== newHeight;

      if (hasChanged) {
        const newSize: Size = { width: newWidth, height: newHeight };
        previousSize.current.width = newWidth;
        previousSize.current.height = newHeight;

        if (onResize.current) {
          onResize.current(newSize);
        }
      }
    });

    observer.observe(ref.current, { box });

    return () => {
      observer.disconnect();
    };
  }, [box, ref, skip]);
}

type BoxSizesKey = keyof Pick<
  ResizeObserverEntry,
  "borderBoxSize" | "contentBoxSize" | "devicePixelContentBoxSize"
>;

function extractSize(
  entry: ResizeObserverEntry,
  box: BoxSizesKey,
  sizeType: keyof ResizeObserverSize,
): number | undefined {
  if (!entry[box]) {
    if (box === "contentBoxSize") {
      return entry.contentRect[sizeType === "inlineSize" ? "width" : "height"];
    }
    return undefined;
  }

  return Array.isArray(entry[box])
    ? entry[box][0][sizeType]
    : // @ts-expect-error Support Firefox's non-standard behavior
      (entry[box][sizeType] as number);
}
