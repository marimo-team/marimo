/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";

interface UseResizeHandleProps {
  onResize?: (width: number) => void;
  startingWidth: number | "contentWidth";
}

// Currently supports left and right resizing
export const useResizeHandle = ({
  onResize,
  startingWidth,
}: UseResizeHandleProps) => {
  const resizableDivRef = useRef<HTMLDivElement>(null);
  const handleRefs = {
    left: useRef<HTMLDivElement>(null),
    right: useRef<HTMLDivElement>(null),
  };

  const leftHandle = handleRefs.left.current;
  const rightHandle = handleRefs.right.current;

  useEffect(() => {
    const resizableDiv = resizableDivRef.current;

    if (!resizableDiv || (!leftHandle && !rightHandle)) {
      return;
    }

    let width = Number.parseInt(window.getComputedStyle(resizableDiv).width);
    let lastX = 0;
    let isResizing = false;

    const mouseMoveHandlers = {
      left: (e: MouseEvent) => onMouseMove(e, "left"),
      right: (e: MouseEvent) => onMouseMove(e, "right"),
    };

    const mouseUpHandlers = {
      left: () => onMouseUp("left"),
      right: () => onMouseUp("right"),
    };

    const mouseDownHandlers = {
      left: (e: MouseEvent) => onMouseDown(e, "left"),
      right: (e: MouseEvent) => onMouseDown(e, "right"),
    };

    const onMouseMove = (e: MouseEvent, resizeDirection: "left" | "right") => {
      if (!resizableDiv || !isResizing) {
        return;
      }

      const dx = e.clientX - lastX;
      lastX = e.clientX;
      // dx is negative when moving left
      width = resizeDirection === "left" ? width - dx : width + dx;
      resizableDiv.style.width = `${width}px`;
    };

    const onMouseUp = (resizeDirection: "left" | "right") => {
      if (isResizing) {
        onResize?.(width);
        isResizing = false;
      }
      document.removeEventListener(
        "mousemove",
        mouseMoveHandlers[resizeDirection],
      );
      document.removeEventListener("mouseup", mouseUpHandlers[resizeDirection]);
    };

    const onMouseDown = (e: MouseEvent, resizeDirection: "left" | "right") => {
      e.preventDefault(); // Prevent selection of elements underneath
      isResizing = true;
      lastX = e.clientX;
      document.addEventListener(
        "mousemove",
        mouseMoveHandlers[resizeDirection],
      );
      document.addEventListener("mouseup", mouseUpHandlers[resizeDirection]);
    };

    if (leftHandle) {
      leftHandle.addEventListener("mousedown", mouseDownHandlers.left);
    }
    if (rightHandle) {
      rightHandle.addEventListener("mousedown", mouseDownHandlers.right);
    }

    return () => {
      if (leftHandle) {
        leftHandle.removeEventListener("mousedown", mouseDownHandlers.left);
        document.removeEventListener("mousemove", mouseMoveHandlers.left);
        document.removeEventListener("mouseup", mouseUpHandlers.left);
      }
      if (rightHandle) {
        rightHandle.removeEventListener("mousedown", mouseDownHandlers.right);
        document.removeEventListener("mousemove", mouseMoveHandlers.right);
        document.removeEventListener("mouseup", mouseUpHandlers.right);
      }
    };
  }, [leftHandle, rightHandle, onResize, resizableDivRef]);

  return {
    resizableDivRef,
    handleRefs,
    style: {
      // Default to medium width
      width:
        startingWidth === "contentWidth"
          ? "var(--content-width-medium)"
          : `${startingWidth}px`,
    },
  };
};
