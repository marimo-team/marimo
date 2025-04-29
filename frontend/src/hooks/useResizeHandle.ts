/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";

interface UseResizeHandleProps {
  onResize?: (width: number) => void;
  startingWidth: number | "contentWidth";
}

export const useResizeHandle = ({
  onResize,
  startingWidth,
}: UseResizeHandleProps) => {
  const resizableDivRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = handleRef.current;
    const resizableDiv = resizableDivRef.current;

    if (!handle || !resizableDiv) {
      return;
    }

    let width = Number.parseInt(window.getComputedStyle(resizableDiv).width);
    let lastX = 0;
    let isResizing = false;

    const onMouseMove = (e: MouseEvent) => {
      if (!resizableDiv || !isResizing) {
        return;
      }
      const dx = e.clientX - lastX;
      lastX = e.clientX;
      width += dx;
      resizableDiv.style.width = `${width}px`;
    };

    const onMouseUp = () => {
      if (isResizing) {
        onResize?.(width);
        isResizing = false;
      }
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    const onMouseDown = (e: MouseEvent) => {
      isResizing = true;
      lastX = e.clientX;
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    };

    handle.addEventListener("mousedown", onMouseDown);

    return () => {
      handle.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, [onResize]);

  return {
    resizableDivRef,
    handleRef,
    style: {
      width:
        typeof startingWidth === "string"
          ? startingWidth
          : `${startingWidth}px`,
    },
  };
};
