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

const svgCache = new LRUCache<
  string,
  Promise<{ svg: string; renderId: string }>
>(64);

// Mermaid reads global config when a render starts.
let renderQueue: Promise<unknown> = Promise.resolve();

function renderDiagram(diagram: string, config: MermaidConfig) {
  const key = JSON.stringify([diagram, config]);
  const cached = svgCache.get(key);
  if (cached) {
    return cached;
  }

  // Temporary render IDs must never match SVGs already owned by React.
  const renderId = `mermaid-${randomAlpha()}`;
  const evict = () => {
    if (svgCache.get(key) === result) {
      svgCache.delete(key);
    }
  };
  const result = renderQueue.then(async () => {
    try {
      // Cached layouts must be measured with the loaded fonts.
      await document.fonts?.ready;
      mermaid.initialize(config);
      const { svg, diagramType } = await mermaid.render(renderId, diagram);
      // Gantt charts draw a "today" marker from the current time.
      if (diagramType === "gantt") {
        evict();
      }
      return { svg, renderId };
    } catch (error) {
      evict();
      Logger.warn("Failed to render mermaid diagram", error);
      throw error;
    } finally {
      // Mermaid leaves its temporary elements behind on some failures.
      document.getElementById(renderId)?.remove();
      document.getElementById(`d${renderId}`)?.remove();
      document.getElementById(`i${renderId}`)?.remove();
    }
  });
  svgCache.set(key, result);
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
    const result = await renderDiagram(trimmedDiagram, {
      ...DEFAULT_CONFIG,
      theme: resolvedTheme as MermaidConfig["theme"],
      themeVariables,
      darkMode,
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
