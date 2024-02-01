/* Copyright 2024 Marimo. All rights reserved. */
import { PanelGroupStorage } from "react-resizable-panels";
import { z } from "zod";
import { Objects } from "@/utils/objects";

const schema = z.record(z.tuple([z.number(), z.number()]));

let storedValue: string | null = null;

/**
 * This does 2 things:
 *  - stores the storage in memory, so it persists across moving the sidebar
 *  - flips the order of the store when the direction is flipped, since the helper sidebar
 *  will either come first or last.
 */
export function createStorage(location: "left" | "bottom"): PanelGroupStorage {
  return {
    getItem(name) {
      if (!storedValue) {
        return storedValue ?? null;
      }
      if (location === "left") {
        return storedValue;
      }

      // flip
      try {
        const parsed = schema.parse(JSON.parse(storedValue));
        return JSON.stringify(
          Objects.mapValues(parsed, (value) => {
            return value.reverse();
          }),
        );
      } catch {
        return null;
      }
    },
    setItem(name, value) {
      if (location !== "left") {
        // flip
        try {
          const parsed = schema.parse(JSON.parse(value));
          value = JSON.stringify(
            Objects.mapValues(parsed, (value) => {
              return value.reverse();
            }),
          );
        } catch {
          return null;
        }
      }

      storedValue = value || null;
    },
  };
}
