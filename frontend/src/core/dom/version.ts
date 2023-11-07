/* Copyright 2023 Marimo. All rights reserved. */

import { invariant } from "@/utils/invariant";

export function getMarimoVersion() {
  const tag = document.querySelector("marimo-version");
  invariant(
    tag !== null && tag instanceof HTMLElement,
    "internal-error: marimo-version tag not found"
  );

  const version = tag.dataset.version;
  invariant(
    version !== undefined,
    "internal-error: marimo-version tag does not have version"
  );

  return version;
}
