/* Copyright 2023 Marimo. All rights reserved. */

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { DownloadIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";

interface Data {
  /**
   * The href to download
   */
  data: string;
  /**
   * Filename
   */
  filename?: string;
  /**
   * Label
   */
  label?: string | null;
}

export class DownloadPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-download";

  validator = z.object({
    data: z.string(),
    label: z.string().nullish(),
    filename: z.string().optional(),
  });

  render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <a
        href={data.data}
        download={data.filename || true}
        className={buttonVariants({ variant: "secondary" })}
      >
        <DownloadIcon className="mr-2 w-3 h-3" />
        {data.label || "Download"}
      </a>
    );
  }
}
