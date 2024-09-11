/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import { OutputRenderer } from "../../components/editor/Output";
import type { OutputMessage } from "@/core/kernel/messages";

interface Data {
  mime: OutputMessage["mimetype"];
  data: string;
}

export class MimeRendererPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-mime-renderer";

  validator = z.object({
    mime: z.string().transform((val) => val as OutputMessage["mimetype"]),
    data: z.string(),
  });

  render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    if (!data) {
      return <div />;
    }
    const parsed = JSON.parse(data.data);
    return (
      <OutputRenderer
        message={{
          data: parsed as OutputMessage["data"],
          channel: "output",
          mimetype: data.mime,
        }}
      />
    );
  }
}
