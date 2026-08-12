/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { SlidersHorizontalIcon } from "lucide-react";
import type React from "react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ExternalLink } from "@/components/ui/links";
import { Switch } from "@/components/ui/switch";
import { useAIConfigActions } from "@/core/ai/config";
import { aiAtom } from "@/core/config/config";
import { cn } from "@/utils/cn";

export const CapabilitiesPopover: React.FC = () => {
  const ai = useAtomValue(aiAtom);
  const webSearchOn = ai?.capabilities?.web_search ?? false;
  const { saveCapabilityChange } = useAIConfigActions();

  return (
    <Popover>
      <PopoverTrigger asChild={true}>
        <Button
          aria-label="Capabilities"
          title="Capabilities"
          variant="text"
          size="icon"
          className={cn(
            "h-6 w-6 shrink-0 bg-muted hover:bg-muted/30",
            webSearchOn && "text-primary",
          )}
        >
          <SlidersHorizontalIcon className="h-3.5 w-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-76 p-3" align="start" side="top">
        <label
          htmlFor="web-search-toggle"
          className="flex items-start justify-between gap-3 cursor-pointer"
        >
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-semibold">Web search</span>
            <span className="text-xs text-muted-foreground">
              Search the web when the model supports it.{" "}
              <ExternalLink href="https://docs.marimo.io/guides/editor_features/tools#web-search-and-fetch">
                Learn more
              </ExternalLink>
            </span>
          </div>
          <Switch
            id="web-search-toggle"
            size="sm"
            checked={webSearchOn}
            onCheckedChange={(checked) =>
              saveCapabilityChange("web_search", checked)
            }
          />
        </label>
      </PopoverContent>
    </Popover>
  );
};
