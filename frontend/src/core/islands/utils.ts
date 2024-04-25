/* Copyright 2024 Marimo. All rights reserved. */
import { initialMode } from "@/core/mode";

export function isIslands() {
  return (import.meta.env.VITE_MARIMO_ISLANDS === true
    || initialMode === "island");
}
