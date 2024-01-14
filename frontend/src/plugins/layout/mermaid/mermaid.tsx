/* Copyright 2023 Marimo. All rights reserved. */
import React, { useRef } from "react";
import mermaid from "mermaid";
import type { MermaidConfig } from "mermaid";
import { useAsyncData } from "@/hooks/useAsyncData";

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

mermaid.initialize({ ...DEFAULT_CONFIG });

const Mermaid: React.FC<Props> = ({ diagram }) => {
  const id = useRef(Math.random().toString(36).slice(2, 6)).current;

  const { data: svg } = useAsyncData(async () => {
    const result = await mermaid
      .render(id, diagram, undefined)
      .catch((error) => {
        document.getElementById(id)?.remove();
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
