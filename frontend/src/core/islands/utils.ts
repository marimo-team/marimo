/* Copyright 2024 Marimo. All rights reserved. */

export function isIslands() {
  // importing "@/core/mode" has the expectation of a valid mode,
  // which is not the case duyring testing.
  const tag = document.querySelector("marimo-mode");
  const initialMode =
    tag === null || !(tag instanceof HTMLElement) ? null : tag.dataset.mode;
  console.log("initialMode", initialMode, tag);
  return (
    import.meta.env.VITE_MARIMO_ISLANDS === true || initialMode === "island"
  );
}
