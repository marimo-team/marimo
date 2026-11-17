/* Copyright 2026 Marimo. All rights reserved. */

import { PlugIcon } from "lucide-react";
import { usePairWithAgentModal } from "@/components/editor/actions/pair-with-agent";
import { Button } from "@/components/ui/button";
import { isWasm } from "@/core/wasm/utils";

const NotebookIllustration = () => (
  <svg
    width="160"
    height="120"
    viewBox="0 0 160 120"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.25"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="text-muted-foreground/50"
    aria-hidden={true}
  >
    <path d="M46 54v38a8 8 0 0 0 8 8h44M80 34h24" strokeDasharray="3 4" />
    <rect
      x="13"
      y="23"
      width="72"
      height="54"
      rx="5"
      className="fill-background"
    />
    <path d="M13 35h72" />
    <circle cx="21" cy="29" r="1" fill="currentColor" stroke="none" />
    <path d="m30 46-5 5 5 5m12-10 5 5-5 5m-6-12-3 14M25 66h36" />
    <g className="text-emerald-700/70 dark:text-emerald-400/70">
      <rect
        x="96"
        y="10"
        width="51"
        height="54"
        rx="5"
        className="fill-background"
      />
      <path d="M106 22v31h31" opacity="0.5" />
      <path d="m111 44 7-8 7 3 11-16" />
      <circle cx="136" cy="23" r="2" className="fill-background" />
    </g>
    <rect
      x="74"
      y="73"
      width="59"
      height="37"
      rx="5"
      className="fill-background"
    />
    <path d="M74 85h59M74 97h59M94 85v25M114 85v25" opacity="0.6" />
    <path d="M82 79h10m8 0h6m8 0h11" />
  </svg>
);

export const ChatEmptyState = () => {
  const openPairWithAgentModal = usePairWithAgentModal();

  return (
    <div className="flex flex-1 flex-col justify-center pb-12">
      <div className="mx-auto flex w-full max-w-xs flex-col items-center gap-5 px-3 py-6">
        <NotebookIllustration />
        <p className="text-center text-xs leading-5 text-muted-foreground">
          Ask questions, write code, build charts, and summarize insights.
        </p>
        {!isWasm() && (
          <Button
            type="button"
            variant="link"
            className="h-auto gap-1.5 p-0 text-xs font-normal"
            onClick={openPairWithAgentModal}
          >
            <PlugIcon className="size-3.5" aria-hidden={true} />
            Pair your own coding agent
          </Button>
        )}
      </div>
    </div>
  );
};
