/* Copyright 2026 Marimo. All rights reserved. */

import { reactLazyWithPreload } from "@/utils/lazy";
import { Logger } from "@/utils/Logger";
import type { PanelType } from "../types";

// Preloading is best-effort: a chunk-load failure here should not surface as
// an unhandled rejection (the panel will retry the import when actually
// rendered, where Suspense/ErrorBoundary handle the failure).
const safePreload = (lazy: { preload: () => Promise<unknown> }) => (): void => {
  void lazy.preload().catch((error) => {
    Logger.debug("Failed to preload panel chunk", error);
  });
};

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
  files: safePreload(LazyFileExplorerPanel),
  variables: safePreload(LazySessionPanel),
  dependencies: safePreload(LazyDependencyGraphPanel),
  packages: safePreload(LazyPackagesPanel),
  outline: safePreload(LazyOutlinePanel),
  documentation: safePreload(LazyDocumentationPanel),
  snippets: safePreload(LazySnippetsPanel),
  ai: () => {
    safePreload(LazyChatPanel)();
    safePreload(LazyAgentPanel)();
  },
  errors: safePreload(LazyErrorsPanel),
  scratchpad: safePreload(LazyScratchpadPanel),
  tracing: safePreload(LazyTracingPanel),
  secrets: safePreload(LazySecretsPanel),
  logs: safePreload(LazyLogsPanel),
  terminal: safePreload(LazyTerminal),
  cache: safePreload(LazyCachePanel),
};
