/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import { lazy } from "react";
import {
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
