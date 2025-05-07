/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";

interface UseResizeHandleProps {
  onResize?: (width: number) => void;
  minWidth?: number;
  maxWidth?: number;
  startingWidth: number | "contentWidth";
}

// Currently supports left and right resizing
export const useResizeHandle = ({
  onResize,
  startingWidth,
  minWidth,
  maxWidth,
}: UseResizeHandleProps) => {
  const resizableDivRef = useRef<HTMLDivElement>(null);
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const resizableDiv = resizableDivRef.current;
    const leftHandle = leftRef.current;
    const rightHandle = rightRef.current;

    // If both handles are missing, it is not resizable
    if (!resizableDiv || (!leftHandle && !rightHandle)) {
      return;
    }

    let width = Number.parseInt(window.getComputedStyle(resizableDiv).width);
    let lastX = 0;
    let isResizing = false;
    let activeDirection: "left" | "right" | null = null;

    const handleMouseMove = (e: MouseEvent) => {
      if (!resizableDiv || !isResizing || !activeDirection) {
        return;
      }

      const dx = e.clientX - lastX;
      lastX = e.clientX;
      // dx is negative when moving left
      width = activeDirection === "left" ? width - dx : width + dx;
      if (minWidth) {
        width = Math.max(minWidth, width);
      }
      if (maxWidth) {
        width = Math.min(maxWidth, width);
      }
      resizableDiv.style.width = `${width}px`;
    };

    const handleMouseUp = () => {
      if (isResizing) {
        onResize?.(width);
        isResizing = false;
        activeDirection = null;
      }
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    const handleMouseDown = (e: MouseEvent, direction: "left" | "right") => {
      e.preventDefault();
      isResizing = true;
      activeDirection = direction;
      lastX = e.clientX;
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    };

    const leftMouseDown = (e: MouseEvent) => handleMouseDown(e, "left");
    const rightMouseDown = (e: MouseEvent) => handleMouseDown(e, "right");

    if (leftHandle) {
      leftHandle.addEventListener("mousedown", leftMouseDown);
    }
    if (rightHandle) {
      rightHandle.addEventListener("mousedown", rightMouseDown);
    }

    return () => {
      if (leftHandle) {
        leftHandle.removeEventListener("mousedown", leftMouseDown);
      }
      if (rightHandle) {
        rightHandle.removeEventListener("mousedown", rightMouseDown);
      }
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [minWidth, maxWidth, onResize]);

  return {
    resizableDivRef,
    handleRefs: {
      left: leftRef,
      right: rightRef,
    },
    style: {
      // Default to medium width
      width:
        startingWidth === "contentWidth"
          ? "var(--content-width-medium)"
          : `${startingWidth}px`,
    },
  };
};
