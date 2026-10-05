/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";
import { z } from "zod";
import { JsonOutput } from "../../components/editor/output/JsonOutput";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

interface Data {
  name?: string | null;
  /**
   * The JSON data to display
   */
  jsonData?: unknown;
  /**
   * The format of the JSON data. Can be 'auto', 'json', or 'yaml'.
   */
  valueTypes?: "json" | "python";
}

export class JsonOutputPlugin implements IStatelessPlugin<Data> {
  public tagName = "marimo-json-output";

  public validator = z.object({
    name: z.string().nullish(),
    jsonData: z.unknown().optional(),
    valueTypes: z.enum(["json", "python"]).default("python"),
  });

  public render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    // `false` defaults to no text label
    const name = data.name === undefined ? false : data.name || "";
    return (
      <JsonOutput
        data={data.jsonData}
        format="auto"
        valueTypes={data.valueTypes}
        name={name}
      />
    );
  }
}
