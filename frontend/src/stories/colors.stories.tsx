/* Copyright 2024 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";

const COLORS = [
  "bg-background",
  "bg-foreground",
  "bg-muted",
  "bg-muted-foreground",
  "bg-popover",
  "bg-popover-foreground",
  "bg-card",
  "bg-card-foreground",
  "bg-border",
  "bg-input",
  "bg-primary",
  "bg-primary-foreground",
  "bg-secondary",
  "bg-secondary-foreground",
  "bg-accent",
  "bg-accent-foreground",
  "bg-destructive",
  "bg-destructive-foreground",
  "bg-error",
  "bg-error-foreground",
  "bg-success",
  "bg-success-foreground",
  "bg-action",
  "bg-action-hover",
  "bg-action-foreground",
  "bg-link",
  "bg-link-visited",
  "bg-ring",
];

const meta: Meta = {
  title: "Variables",
  args: {},
};

export default meta;

export const Colors: StoryObj = {
  render: () => {
    return (
      <div className="grid grid-cols-5 gap-4 p-4">
        {COLORS.map((color) => (
          <div
            key={color}
            className="flex flex-col items-center justify-center gap-2"
          >
            <div
              className={`h-24 w-24 rounded-md ${color} flex items-center justify-center border`}
            />
            <span className="text-sm text-center">{color.slice(3)}</span>
          </div>
        ))}
      </div>
    );
  },
};

const ROUND = [
  "rounded-none",
  "rounded-sm",
  "rounded-md",
  "rounded-lg",
  "rounded-xl",
  "rounded-2xl",
  "rounded-3xl",
  "rounded-full",
];

export const Round: StoryObj = {
  render: () => {
    return (
      <div className="grid grid-cols-5 gap-4 p-4">
        {ROUND.map((round) => (
          <div
            key={round}
            className="flex flex-col items-center justify-center gap-2"
          >
            <div
              className={`h-24 w-24 bg-muted flex items-center justify-center border ${round}`}
            />
            <span className="text-sm text-center">{round.slice(8)}</span>
          </div>
        ))}
      </div>
    );
  },
};

const SHADOWS = [
  "shadow-xs",
  "shadow-sm",
  "shadow-md",
  "shadow-lg",
  "shadow-xl",
  "shadow-2xl",
  "shadow-inner",
  "shadow-none",
];

const COLORED_SHADOWS = [
  "shadow-xs shadow-blue-500",
  "shadow-sm shadow-blue-500",
  "shadow-md shadow-blue-500",
  "shadow-lg shadow-blue-500",
  "shadow-xl shadow-blue-500",
  "shadow-2xl shadow-blue-500",
  "shadow-inner shadow-blue-500",
];

const SOLID_SHADOWS = [
  "shadow-xsSolid",
  "shadow-smSolid",
  "shadow-mdSolid",
  "shadow-lgSolid",
  "shadow-xlSolid",
  "shadow-2xlSolid",
];

const MISC = [
  "shadow-smSolid shadow-accent",
  "shadow-mdSolid shadow-accent",
  "shadow-smSolid shadow-error",
  "shadow-mdSolid shadow-error",
];

export const Shadows: StoryObj = {
  render: () => {
    const renderShadows = (shadows: string[]) => (
      <div className="grid grid-cols-5 gap-4 p-4">
        {shadows.map((shadow) => (
          <div
            key={shadow}
            className="flex flex-col items-center justify-center gap-2"
          >
            <div
              className={`h-24 w-24 bg-muted flex items-center justify-center border ${shadow}`}
            />
            <span className="text-sm text-center">{shadow.slice(7)}</span>
          </div>
        ))}
      </div>
    );
    return (
      <div className="flex flex-col">
        {renderShadows(SHADOWS)}
        {renderShadows(COLORED_SHADOWS)}
        {renderShadows(SOLID_SHADOWS)}
        {renderShadows(MISC)}
      </div>
    );
  },
};
