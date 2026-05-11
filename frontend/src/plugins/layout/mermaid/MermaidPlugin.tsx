/* Copyright 2026 Marimo. All rights reserved. */

import { type JSX, lazy } from "react";
import { z } from "zod";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "@/plugins/stateless-plugin";

interface Data {
  diagram: string;
  theme?: string;
  theme_variables?: Record<string, string>;
}

export class MermaidPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-mermaid";

  validator = z.object({
    diagram: z.string(),
    theme: z.string().optional(),
    theme_variables: z.record(z.string(), z.string()).optional(),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <LazyMermaid
        diagram={props.data.diagram}
        theme={props.data.theme}
        themeVariables={props.data.theme_variables}
      />
    );
  }
}

const LazyMermaid = lazy(() => import("./mermaid"));
