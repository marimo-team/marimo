/* Copyright 2024 Marimo. All rights reserved. */
import React, { useState } from "react";
import mermaid from "mermaid";
import type { MermaidConfig } from "mermaid";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Logger } from "@/utils/Logger";
import { useTheme } from "@/theme/useTheme";

interface Props {
  diagram: string;
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

function randomAlpha() {
  const alphabet = "abcdefghijklmnopqrstuvwxyz";
  const length = 6;
  return Array.from(
    { length },
    () => alphabet[Math.floor(Math.random() * alphabet.length)],
  ).join("");
}

const Mermaid: React.FC<Props> = ({ diagram }) => {
  // eslint-disable-next-line react/hook-use-state
  const [id] = useState(() => randomAlpha());

  const darkMode = useTheme().theme === "dark";
  mermaid.initialize({
    ...DEFAULT_CONFIG,
    theme: darkMode ? "dark" : "forest",
    darkMode: darkMode,
  });

  const { data: svg } = useAsyncData(async () => {
    const result = await mermaid
      .render(id, diagram, undefined)
      .catch((error) => {
        document.getElementById(id)?.remove();
        Logger.warn("Failed to render mermaid diagram", error);
        throw error;
      });

    return result.svg;
  }, [diagram, id]);

  if (!svg) {
    return null;
  }

  return <div dangerouslySetInnerHTML={{ __html: svg }} />;
};

export default Mermaid;
