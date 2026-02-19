/* Copyright 2026 Marimo. All rights reserved. */
import { asURL } from "./url";

/**
 * Open a notebook in a new tab.
 * @param path - The path to the notebook.
 */
export function openNotebook(path: string) {
  // There is no leading `/` in the path in order to work when marimo is at a subpath.
  window.open(asURL(`?file=${encodeURIComponent(path)}`).toString(), "_blank");
}
