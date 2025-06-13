/* Copyright 2024 Marimo. All rights reserved. */

import type { JSX } from "react";
import { z } from "zod";
import type { OutputMessage } from "@/core/kernel/messages";
import { OutputRenderer } from "../../components/editor/Output";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

interface Data {
  mime: OutputMessage["mimetype"];
  data: OutputMessage["data"] | null;
}

export class MimeRendererPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-mime-renderer";

  validator = z.object({
    mime: z.string().transform((val) => val as OutputMessage["mimetype"]),
    data: z.union([
      z.string(),
      z.null(),
      z.record(z.unknown()),
      z.array(z.any()),
    ]),
  });

  render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    if (!data.data) {
      return <div />;
    }

    return (
      <OutputRenderer
        message={{
          data: data.data,
          channel: "output",
          mimetype: data.mime,
        }}
      />
    );
  }
}
