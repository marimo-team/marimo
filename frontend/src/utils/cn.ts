/* Copyright 2026 Marimo. All rights reserved. */

import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// tailwind-merge only knows the default font-size scale. Custom --text-*
// tokens from globals.css must be registered here, otherwise it treats
// `text-<token>` as a text color and drops it next to a real color class.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        { text: ["3xs", "2xs", "xs-plus", "sm-minus", "10", "11", "13"] },
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
