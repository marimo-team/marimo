/* Copyright 2024 Marimo. All rights reserved. */

import clsx from "clsx";
import { Circle } from "lucide-react";
import React from "react";

interface LoadingEllipsisProps {
  /** Extra Tailwind classes */
  className?: string;
  /** Diameter of each dot in pixels */
  size?: number;
  /** Tailwind gap utility between dots (e.g. "gap-1" or "gap-2") */
  gap?: string;
  /** Pulse cycle length in milliseconds */
  durationMs?: number;
}

const LoadingEllipsis: React.FC<LoadingEllipsisProps> = ({
  className,
  size = 8,
  gap = "gap-1",
  durationMs = 1200,
}) => {
  const baseStyle: React.CSSProperties = {
    animationDuration: `${durationMs}ms`,
  };

  return (
    <div className={clsx("flex", gap, className)} aria-label="Loading">
      {[0, 1, 2].map((i) => (
        <Circle
          key={i}
          width={size}
          height={size}
          className="fill-current text-current animate-ellipsis-dot"
          style={{
            ...baseStyle,
            animationDelay: `${(durationMs / 3) * i}ms`,
          }}
        />
      ))}
    </div>
  );
};

export { LoadingEllipsis };
