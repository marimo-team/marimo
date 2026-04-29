/* Copyright 2026 Marimo. All rights reserved. */

import type { RuntimeCell } from "@/core/cells/types";
import { Logger } from "@/utils/Logger";

/**
 * Build-time stub for `@/components/slides/slide-cell-view`, wired up via
 * `resolve.alias` in `frontend/islands/vite.config.mts`. Islands embeds gate
 * off the slides "show code" toggle entirely (see `useNotebookCodeAvailable`
 * + `isIslands()`), so neither view is reachable at runtime there.
 *
 * Replacing the module at build time keeps the entire CodeMirror /
 * Codeium / `@bufbuild/protobuf` import subtree out of the islands bundle,
 * which both shrinks the bundle and lets `islands/validate.sh` pass — the
 * upstream protobuf code contains a `process.env.BUF_BIGINT_DISABLE`
 * runtime check that the validator otherwise flags.
 */
export const SlideCellView = (_props: { cell: RuntimeCell }) => {
  Logger.warn(
    "SlideCellView islands stub rendered; this should never happen in a read-only embed.",
  );
  return null;
};

export const SlideCellReadOnlyView = (_props: { cell: RuntimeCell }) => {
  Logger.warn(
    "SlideCellReadOnlyView islands stub rendered; this should never happen in a read-only embed.",
  );
  return null;
};
