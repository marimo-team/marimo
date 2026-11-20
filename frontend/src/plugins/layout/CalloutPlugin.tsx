/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";
import { z } from "zod";
import { CalloutOutput } from "../../components/editor/output/CalloutOutput";
import { type Intent, zodIntent } from "../impl/common/intent";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

interface Data {
  /**
   * The html to render
   */
  html: string;
  /**
   * The kind of callout
   */
  kind: Intent;
  /**
   * An optional bold title line
   */
  title?: string;
}

export class CalloutPlugin implements IStatelessPlugin<Data> {
  public tagName = "marimo-callout-output";

  public validator = z.object({
    html: z.string(),
    kind: zodIntent,
    title: z.string().optional(),
  });

  public render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <CalloutOutput html={data.html} kind={data.kind} title={data.title} />
    );
  }
}
