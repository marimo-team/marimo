/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import { JsonOutput } from "../../components/editor/output/JsonOutput";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import { EmotionCacheProvider } from "../../components/editor/output/EmotionCacheProvider";

interface Data {
  name?: string | null;
  /**
   * The JSON data to display
   */
  jsonData?: unknown;
}

export class JsonOutputPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-json-output";

  validator = z.object({
    name: z.string().nullish(),
    jsonData: z.unknown(),
  });

  render({ data, host }: IStatelessPluginProps<Data>): JSX.Element {
    // `false` defaults to no text label
    const name = data.name === undefined ? false : data.name || "";
    return (
      <EmotionCacheProvider container={host.shadowRoot}>
        <JsonOutput data={data.jsonData} format="auto" name={name} />
      </EmotionCacheProvider>
    );
  }
}
