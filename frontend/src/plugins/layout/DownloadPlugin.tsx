/* Copyright 2024 Marimo. All rights reserved. */

import { DownloadIcon, Loader2 } from "lucide-react";
import { useState } from "react";
import { z } from "zod";
import { buttonVariants } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import { cn } from "@/utils/cn";
import { downloadByURL } from "@/utils/download";
import { Logger } from "@/utils/Logger";
import { createPlugin } from "../core/builder";
import { renderHTML } from "../core/RenderHTML";
import { rpc } from "../core/rpc";

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
  /**
   * Whether to load data lazily
   */
  lazy?: boolean;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type Functions = {
  /**
   * Function to call for lazy loading
   */
  load: (empty: {}) => Promise<{
    /**
     * URL or data-uri
     */
    data: string;
    filename?: string | null | undefined;
  }>;
};
export const DownloadPlugin = createPlugin("marimo-download")
  .withData(
    z.object({
      data: z.string(),
      disabled: z.boolean().default(false),
      filename: z.string().nullish(),
      label: z.string().nullish(),
      lazy: z.boolean().default(false),
    }),
  )
  .withFunctions<Functions>({
    load: rpc.input(z.object({})).output(
      z.object({
        data: z.string(),
        filename: z.string().nullish(),
      }),
    ),
  })
  .renderer((props) => (
    <DownloadButton data={props.data} {...props.functions} />
  ));

const DownloadButton = ({
  data,
  load,
}: {
  data: Data;
  load: Functions["load"];
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    if (!data.lazy) {
      return;
    }

    if (data.disabled) {
      return;
    }

    e.preventDefault();
    setIsLoading(true);

    try {
      const loadedData = await load({});
      downloadByURL(
        loadedData.data,
        loadedData.filename || data.filename || "download",
      );
    } catch (error) {
      toast({
        title: "Failed to download",
        description: "Please try again.",
      });
      Logger.error("Failed to download:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const Icon = isLoading ? Loader2 : DownloadIcon;
  const label = data.label ? renderHTML({ html: data.label }) : "Download";

  return (
    <a
      href={data.data}
      download={data.filename || true}
      target="_blank"
      rel="noopener noreferrer"
      onClick={handleClick}
      className={buttonVariants({
        variant: "secondary",
        disabled: data.disabled || isLoading,
      })}
    >
      <Icon
        className={cn(
          "w-3 h-3",
          data.label && "mr-2",
          isLoading && "animate-spin",
        )}
      />
      {label}
    </a>
  );
};
