/* Copyright 2023 Marimo. All rights reserved. */

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { CalloutOutput } from "../../editor/output/CalloutOutput";

interface Data {
  /**
   * The html to render
   */
  html: string;
  /**
   * The kind of callout
   */
  kind: "neutral" | "alert" | "warn" | "success";
}

export class CalloutPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-callout-output";

  validator = z.object({
    html: z.string(),
    kind: z.enum(["neutral", "alert", "warn", "success"]),
  });

  render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    return <CalloutOutput html={data.html} kind={data.kind} />;
  }
}
