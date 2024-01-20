/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
import { DownloadIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/utils/cn";

interface Data {
  /**
   * The href to download
   */
  data: string;
  /**
   * Filename
   */
  filename?: string | null;
  /**
   * Disabled
   */
  disabled?: boolean;
  /**
   * Button label
   */
  label?: string | null;
}

export class DownloadPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-download";

  validator = z.object({
    data: z.string(),
    disabled: z.boolean().default(false),
    filename: z.string().nullish(),
    label: z.string().nullish(),
  });

  render({ data }: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <a
        href={data.data}
        download={data.filename || true}
        target="_blank"
        rel="noopener noreferrer"
        className={buttonVariants({
          variant: "secondary",
          disabled: data.disabled,
        })}
      >
        <DownloadIcon className={cn("w-3 h-3", data.label && "mr-2")} />
        {data.label ?? "Download"}
      </a>
    );
  }
}
