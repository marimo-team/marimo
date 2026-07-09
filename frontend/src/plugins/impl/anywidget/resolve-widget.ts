/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import type { AnyWidget } from "@anywidget/types";
import { Logger } from "@/utils/Logger";
import { hasFunctionProperty, isRecord } from "@/utils/records";

export function isAnyWidgetModule(mod: any): mod is { default: AnyWidget } {
  if (!mod.default) {
    return false;
  }

  return (
    typeof mod.default === "function" ||
    typeof mod.default?.render === "function" ||
    typeof mod.default?.initialize === "function"
  );
}

const warnedLegacyNamedExportUrls = new Set<string>();
// Cache the synthesized widget per module namespace so its identity stays
// stable across re-renders (like a default export), avoiding needless
// WidgetBinding re-initialization.
const legacyWidgetCache = new WeakMap<object, AnyWidget>();

/**
 * Resolve the AnyWidget from a loaded module: prefer the AFM-spec default
 * export, otherwise synthesize one from legacy named `render`/`initialize`
 * exports. Returns null if neither is present.
 */
export function resolveAnyWidget(mod: any, jsUrl: string): AnyWidget | null {
  if (isAnyWidgetModule(mod)) {
    return mod.default;
  }

  // Only fall back to legacy (pre-AFM) named exports when there is no default
  // export at all; a present-but-invalid default should surface an error
  // rather than be masked.
  if (mod?.default != null) {
    return null;
  }

  const hasNamedRender = typeof mod?.render === "function";
  const hasNamedInitialize = typeof mod?.initialize === "function";
  if (!hasNamedRender && !hasNamedInitialize) {
    return null;
  }

  const cached = legacyWidgetCache.get(mod);
  if (cached) {
    return cached;
  }

  if (!warnedLegacyNamedExportUrls.has(jsUrl)) {
    warnedLegacyNamedExportUrls.add(jsUrl);
    Logger.warn(
      `Anywidget module at ${jsUrl} uses deprecated top-level named ` +
        "exports (`render`/`initialize`). Per the AFM spec, use a default " +
        "export instead: `export default { render }`. " +
        "See https://anywidget.dev/en/afm/",
    );
  }

  const widget: AnyWidget = { render: mod.render, initialize: mod.initialize };
  legacyWidgetCache.set(mod, widget);
  return widget;
}

export function getInvalidAnyWidgetModuleError(
  mod: unknown,
  jsUrl: string,
): Error {
  const afmDocs = "https://anywidget.dev/en/afm/";
  const hasNamedRender = isRecord(mod) && hasFunctionProperty(mod, "render");
  const hasNamedInitialize =
    isRecord(mod) && hasFunctionProperty(mod, "initialize");

  if (hasNamedRender || hasNamedInitialize) {
    const namedExports = [
      hasNamedRender ? "`render`" : null,
      hasNamedInitialize ? "`initialize`" : null,
    ]
      .filter(Boolean)
      .join(" and ");
    const lifecycleHooks = [
      hasNamedRender ? "render" : null,
      hasNamedInitialize ? "initialize" : null,
    ].filter((hook): hook is string => hook !== null);
    const defaultExportExample = `export default { ${lifecycleHooks.join(", ")} }`;
    const namedExportExample =
      lifecycleHooks.length === 1
        ? `export function ${lifecycleHooks[0]}`
        : "named export function ...";
    return new Error(
      `Anywidget module at ${jsUrl} uses named exports (${namedExports}). ` +
        "Per the AFM spec, use a default export instead: " +
        `\`${defaultExportExample}\` (not \`${namedExportExample}\`). ` +
        `See ${afmDocs}`,
    );
  }

  if (!isRecord(mod) || mod.default === undefined) {
    return new Error(
      `Anywidget module at ${jsUrl} is missing a default export. ` +
        "Per the AFM spec, use `export default { render }` or " +
        "`export default async () => ({ render })`. " +
        `See ${afmDocs}`,
    );
  }

  return new Error(
    `Anywidget module at ${jsUrl} has an invalid default export. ` +
      "Expected a factory function or an object with `render` or `initialize`. " +
      `See ${afmDocs}`,
  );
}
