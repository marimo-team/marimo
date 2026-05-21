/* Copyright 2026 Marimo. All rights reserved. */

import { reactLazyWithPreload } from "@/utils/lazy";
import type { PanelType } from "../types";

// Centralized lazy panels. Using reactLazyWithPreload (instead of React.lazy)
// gives each panel a .preload() method so the chunk can be fetched on intent
// (hovering the sidebar icon or developer-panel tab) before the user clicks.

export const LazyTerminal = reactLazyWithPreload(
  () => import("@/components/terminal/terminal"),
);
export const LazyChatPanel = reactLazyWithPreload(
  () => import("@/components/chat/chat-panel"),
);
export const LazyAgentPanel = reactLazyWithPreload(
  () => import("@/components/chat/acp/agent-panel"),
);
export const LazyDependencyGraphPanel = reactLazyWithPreload(
  () => import("../panels/dependency-graph-panel"),
);
export const LazySessionPanel = reactLazyWithPreload(
  () => import("../panels/session-panel"),
);
export const LazyDocumentationPanel = reactLazyWithPreload(
  () => import("../panels/documentation-panel"),
);
export const LazyErrorsPanel = reactLazyWithPreload(
  () => import("../panels/error-panel"),
);
export const LazyFileExplorerPanel = reactLazyWithPreload(
  () => import("../panels/file-explorer-panel"),
);
export const LazyLogsPanel = reactLazyWithPreload(
  () => import("../panels/logs-panel"),
);
export const LazyOutlinePanel = reactLazyWithPreload(
  () => import("../panels/outline-panel"),
);
export const LazyPackagesPanel = reactLazyWithPreload(
  () => import("../panels/packages-panel"),
);
export const LazyScratchpadPanel = reactLazyWithPreload(
  () => import("../panels/scratchpad-panel"),
);
export const LazySecretsPanel = reactLazyWithPreload(
  () => import("../panels/secrets-panel"),
);
export const LazySnippetsPanel = reactLazyWithPreload(
  () => import("../panels/snippets-panel"),
);
export const LazyTracingPanel = reactLazyWithPreload(
  () => import("../panels/tracing-panel"),
);
export const LazyCachePanel = reactLazyWithPreload(
  () => import("../panels/cache-panel"),
);

// Preloader registry: hovering an icon/tab calls into this map to warm the
// corresponding chunk. Two panel types (chat and agents) share the "ai" slot,
// so we preload both.
export const PANEL_PRELOADERS: Record<PanelType, () => void> = {
  files: LazyFileExplorerPanel.preload,
  variables: LazySessionPanel.preload,
  dependencies: LazyDependencyGraphPanel.preload,
  packages: LazyPackagesPanel.preload,
  outline: LazyOutlinePanel.preload,
  documentation: LazyDocumentationPanel.preload,
  snippets: LazySnippetsPanel.preload,
  ai: () => {
    LazyChatPanel.preload();
    LazyAgentPanel.preload();
  },
  errors: LazyErrorsPanel.preload,
  scratchpad: LazyScratchpadPanel.preload,
  tracing: LazyTracingPanel.preload,
  secrets: LazySecretsPanel.preload,
  logs: LazyLogsPanel.preload,
  terminal: LazyTerminal.preload,
  cache: LazyCachePanel.preload,
};
