/* Copyright 2024 Marimo. All rights reserved. */
import { cva } from "class-variance-authority";
import "./Inputs.css";

export const button = cva(
  "flex items-center justify-center m-0 leading-none font-medium border border-foreground/10 shadow-xsSolid shadow-foreground/10 hover:cursor-pointer focus:shadow-md dark:border-border text-sm",
  {
    variants: {
      color: {
        // neutral, but contrasts against background
        gray: "mo-button gray",
        // neutral, relying on border and shadow to stand out
        white: "mo-button white",
        green: "mo-button green",
        // for destructive actions
        red: "mo-button red",
        // for actions that users should be alerted to
        yellow: "mo-button yellow",
        // for actions that will change state but are not destructive
        "hint-green": "mo-button hint-green",
        disabled: "mo-button disabled",
      },
      shape: {
        rectangle: "rounded",
        circle: "rounded-full",
      },
      size: {
        small: "",
        medium: "",
      },
    },

    compoundVariants: [
      {
        size: "small",
        shape: "circle",
        class: "h-[24px] w-[24px] px-[5.5px] py-[5.5px]",
      },
      {
        size: "medium",
        shape: "circle",
        class: "px-2 py-2",
      },
      {
        size: "small",
        shape: "rectangle",
        class: "px-1 py-1 h-[24px] w-[24px]",
      },
      {
        size: "medium",
        shape: "rectangle",
        class: "px-3 py-2",
      },
    ],

    defaultVariants: {
      color: "gray",
      size: "medium",
      shape: "rectangle",
    },
  },
);

export const input = cva(
  "font-mono w-full flex-1 inline-flex items-center justify-center rounded px-2.5 text-foreground/60 h-[36px] hover:shadow-md hover:cursor-pointer focus:shadow-md focus:outline-none text-[hsl(0, 0%, 43.5%)] bg-transparent hover:bg-background focus:bg-background",
);
