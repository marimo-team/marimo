/* Copyright 2023 Marimo. All rights reserved. */
import { PanelGroupStorage } from "react-resizable-panels";
import { z } from "zod";
import Cookies from "js-cookie";
import { Objects } from "@/utils/objects";

const schema = z.record(z.tuple([z.number(), z.number()]));

/**
 * This does 2 things:
 *  - stores the storage in Cookies, so it persists across sessions and ports
 *  - flips the order of the store when the direction is flipped, since the helper sidebar
 *  will either come first or last.
 */
export function createStorage(location: "left" | "bottom"): PanelGroupStorage {
  return {
    getItem(name) {
      const item = Cookies.get(name);
      if (!item) {
        return item ?? null;
      }
      if (location === "left") {
        return item;
      }

      // flip
      try {
        const parsed = schema.parse(JSON.parse(item));
        return JSON.stringify(
          Objects.mapValues(parsed, (value) => {
            return value.reverse();
          })
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
            })
          );
        } catch {
          return null;
        }
      }

      return Cookies.set(name, value);
    },
  };
}
