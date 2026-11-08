/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { SlidersHorizontalIcon } from "lucide-react";
import type React from "react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { chatOptionsAtom } from "@/core/ai/state";

export const CapabilitiesPopover: React.FC = () => {
  const [chatOptions, setChatOptions] = useAtom(chatOptionsAtom);
  const webSearchOn = chatOptions.webSearch;

  return (
    <Popover>
      <PopoverTrigger asChild={true}>
        <Button
          aria-label="Capabilities"
          title={
            webSearchOn ? "Capabilities (web search enabled)" : "Capabilities"
          }
          data-active={webSearchOn || undefined}
          variant="text"
          size="icon"
          className="chat-control h-6 w-6 shrink-0"
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
              Search the web when the model supports it.
            </span>
          </div>
          <Switch
            id="web-search-toggle"
            aria-label="Web search"
            size="sm"
            checked={webSearchOn}
            onCheckedChange={(webSearch) =>
              setChatOptions((options) => ({ ...options, webSearch }))
            }
          />
        </label>
      </PopoverContent>
    </Popover>
  );
};
