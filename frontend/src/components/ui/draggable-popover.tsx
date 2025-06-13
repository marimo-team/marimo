/* Copyright 2024 Marimo. All rights reserved. */

import type * as PopoverPrimitive from "@radix-ui/react-popover";
import { GripHorizontalIcon } from "lucide-react";
import { useRef, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";

interface DraggablePopoverProps extends PopoverPrimitive.PopoverProps {
  children: React.ReactNode;
  className?: string;
}

export const DraggablePopover = ({
  children,
  className,
  ...props
}: DraggablePopoverProps) => {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const dragStartPos = useRef({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = (e: React.MouseEvent) => {
    dragStartPos.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    };
    setIsDragging(true);
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent) => {
    setPosition({
      x: e.clientX - dragStartPos.current.x,
      y: e.clientY - dragStartPos.current.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
  };

  return (
    <Popover {...props}>
      <PopoverTrigger />
      <PopoverContent
        className={className}
        style={{
          position: "fixed",
          left: position.x,
          top: position.y,
        }}
      >
        <div
          onMouseDown={handleMouseDown}
          className={`flex items-center justify-center absolute top-0 left-1/2 -translate-x-1/2 ${
            isDragging ? "cursor-grabbing" : "cursor-grab"
          }`}
        >
          <GripHorizontalIcon className="h-5 w-5 mt-1 text-muted-foreground/40" />
        </div>
        {children}
      </PopoverContent>
    </Popover>
  );
};
