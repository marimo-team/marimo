/* Copyright 2026 Marimo. All rights reserved. */

import type { MermaidConfig } from "mermaid";
import mermaid from "mermaid";
import React, { useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { useTheme } from "@/theme/useTheme";
import { Logger } from "@/utils/Logger";
import { LRUCache } from "@/utils/lru";

interface Props {
  diagram: string;
  theme?: string;
  themeVariables?: Record<string, string>;
  config?: MermaidConfig;
}

const DEFAULT_CONFIG: MermaidConfig = {
  startOnLoad: true,
  theme: "forest",
  logLevel: "fatal",
  securityLevel: "strict",
  fontFamily: "var(--text-font)",
  arrowMarkerAbsolute: false,
  flowchart: {
    htmlLabels: true,
    curve: "linear",
  },
  sequence: {
    diagramMarginX: 50,
    diagramMarginY: 10,
    actorMargin: 50,
    width: 150,
    height: 65,
    boxMargin: 10,
    boxTextMargin: 5,
    noteMargin: 10,
    messageMargin: 35,
    mirrorActors: true,
    bottomMarginAdj: 1,
    useMaxWidth: true,
    rightAngles: false,
    showSequenceNumbers: false,
  },
  gantt: {
    titleTopMargin: 25,
    barHeight: 20,
    barGap: 4,
    topPadding: 50,
    leftPadding: 75,
    gridLineStartPadding: 35,
    fontSize: 11,
    numberSectionStyles: 4,
    axisFormat: "%Y-%m-%d",
  },
};

// Avoid re-rendering unchanged diagrams. Promises are cached to
// de-duplicate concurrent render requests.
const svgCache = new LRUCache<
  string,
  Promise<{ svg: string; renderId: string }>
>(64);

// Gantt charts draw a "today" marker from the current time.
const TIME_DEPENDENT_DIAGRAM_TYPES = new Set(["gantt"]);

// mermaid's config is global and read when a render starts, so concurrent
// diagrams with different themes could otherwise render with each other's
// config (and that SVG would be cached under the wrong key).
let renderQueue: Promise<unknown> = Promise.resolve();

function renderWithConfig(id: string, diagram: string, config: MermaidConfig) {
  const result = renderQueue.then(() => {
    mermaid.initialize(config);
    return mermaid.render(id, diagram, undefined);
  });
  renderQueue = result.catch(() => undefined);
  return result;
}

function randomAlpha() {
  const alphabet = "abcdefghijklmnopqrstuvwxyz";
  const length = 12;
  return Array.from(
    { length },
    () => alphabet[Math.floor(Math.random() * alphabet.length)],
  ).join("");
}

const Mermaid: React.FC<Props> = ({ diagram, theme, themeVariables }) => {
  // Long and prefixed to prevent collisions with SVG diagram text; when reading
  // from the cache, we use replaceAll to swap the id.
  // oxlint-disable-next-line react/hook-use-state
  const [id] = useState(() => `mermaid-${randomAlpha()}`);

  const darkMode = useTheme().theme === "dark";
  const resolvedTheme = theme ?? (darkMode ? "dark" : "forest");

  // Frontmatter does not work with newlines, so we trim the diagram to avoid these errors
  const trimmedDiagram = diagram.trim();

  const { data: svg, error } = useAsyncData(async () => {
    const key = JSON.stringify([
      trimmedDiagram,
      resolvedTheme,
      darkMode,
      themeVariables,
    ]);
    let cached = svgCache.get(key);
    if (cached === undefined) {
      cached = renderWithConfig(id, trimmedDiagram, {
        ...DEFAULT_CONFIG,
        theme: resolvedTheme as MermaidConfig["theme"],
        themeVariables,
        darkMode,
      }).then((result) => {
        if (TIME_DEPENDENT_DIAGRAM_TYPES.has(result.diagramType)) {
          svgCache.delete(key);
        }
        return { svg: result.svg, renderId: id };
      });
      svgCache.set(key, cached);
    }
    const result = await cached.catch((error) => {
      svgCache.delete(key);
      document.getElementById(id)?.remove();
      Logger.warn("Failed to render mermaid diagram", error);
      throw error;
    });

    // The SVG's styles and markers are scoped by its render id.
    return result.svg.replaceAll(result.renderId, id);
  }, [trimmedDiagram, id, darkMode, resolvedTheme, themeVariables]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!svg) {
    return null;
  }

  return <div dangerouslySetInnerHTML={{ __html: svg }} />;
};

export default Mermaid;
