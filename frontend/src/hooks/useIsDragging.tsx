/* Copyright 2026 Marimo. All rights reserved. */
import React, { useState } from "react";

const OFFSET = 10;

/**
 * Returns whether the user is currently dragging an element.
 * Includes an offset to prevent accidental dragging.
 */
export function useIsDragging() {
  const [mouseIsDown, setMouseIsDown] = useState(false);
  const [initialPosition, setInitialPosition] = React.useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = React.useState(false);

  const handleDragStart = (event: MouseEvent) => {
    setMouseIsDown(true);
    setInitialPosition({ x: event.clientX, y: event.clientY });
  };

  const handleDragMove = (event: MouseEvent) => {
    if (mouseIsDown) {
      const dx = event.clientX - initialPosition.x;
      const dy = event.clientY - initialPosition.y;
      setIsDragging(Math.hypot(dx, dy) > OFFSET);
    }
  };

  const handleDragStop = () => {
    setMouseIsDown(false);
    setIsDragging(false);
  };

  return {
    isDragging: mouseIsDown && isDragging,
    onDragStart: handleDragStart,
    onDragMove: handleDragMove,
    onDragStop: handleDragStop,
  };
}
