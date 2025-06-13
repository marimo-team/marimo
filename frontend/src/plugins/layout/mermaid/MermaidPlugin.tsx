/* Copyright 2024 Marimo. All rights reserved. */

import { type JSX, lazy } from "react";
import { z } from "zod";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "@/plugins/stateless-plugin";

interface Data {
  diagram: string;
}

export class MermaidPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-mermaid";

  validator = z.object({
    diagram: z.string(),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return <LazyMermaid diagram={props.data.diagram} />;
  }
}

const LazyMermaid = lazy(() => import("./mermaid"));
