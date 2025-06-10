/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import { CalloutOutput } from "../../components/editor/output/CalloutOutput";
import { type Intent, zodIntent } from "../impl/common/intent";

import type { JSX } from "react";

interface Data {
  /**
   * The html to render
   */
  html: string;
  /**
   * The kind of callout
   */
  kind: Intent;
}

export class CalloutPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-callout-output";

  validator = z.object({
    html: z.string(),
    kind: zodIntent,
  });

  render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    return <CalloutOutput html={data.html} kind={data.kind} />;
  }
}
