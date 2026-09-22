/* Copyright 2026 Marimo. All rights reserved. */

import { BotIcon } from "lucide-react";
import React from "react";
import { AiProviderIcon } from "@/components/ai/ai-provider-icon";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Button, type ButtonProps } from "@/components/ui/button";
import { isWasm } from "@/core/wasm/utils";
import { cn } from "@/utils/cn";
import { PairWithAgentModal } from "./pair-with-agent-modal";

const FEATURED_AGENTS = [
  { id: "claude", label: "Claude Code" },
  { id: "codex", label: "Codex" },
  { id: "cursor", label: "Cursor" },
  { id: "gemini", label: "Gemini CLI" },
  { id: "opencode", label: "OpenCode" },
  { id: "github", label: "GitHub Copilot" },
  { id: "openai-compatible", label: "Any local agent" },
] as const satisfies ReadonlyArray<{
  id: React.ComponentProps<typeof AiProviderIcon>["provider"];
  label: string;
}>;

export const usePairWithAgentModal = () => {
  const { openModal, closeModal } = useImperativeModal();

  return React.useCallback(
    () => openModal(<PairWithAgentModal onClose={closeModal} />),
    [openModal, closeModal],
  );
};

export const PairWithAgentButton: React.FC<
  ButtonProps & { label?: string }
> = ({ className, label = "Pair with an agent", onClick, ...props }) => {
  const openPairWithAgentModal = usePairWithAgentModal();

  if (isWasm()) {
    return null;
  }

  return (
    <Button
      type="button"
      variant="link"
      size="xs"
      className={cn("h-auto gap-1 px-0", className)}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) {
          openPairWithAgentModal();
        }
      }}
      {...props}
    >
      {label}
    </Button>
  );
};

export const PairWithAgentBanner: React.FC<{
  label?: string;
  className?: string;
}> = ({ label = "Pair with an agent", className }) => {
  const openPairWithAgentModal = usePairWithAgentModal();

  if (isWasm()) {
    return null;
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-(--blue-6) bg-(--blue-2)/50 p-3",
        className,
      )}
    >
      <div className="flex items-center gap-2 text-sm font-semibold">
        {label}
        <fieldset
          className="m-0 flex min-w-0 -space-x-1.5 border-0 p-0 mb-0.5"
          aria-label="Supported agents"
        >
          {FEATURED_AGENTS.map(({ id, label }) => (
            <figure
              key={id}
              title={label}
              aria-label={label}
              className="m-0 flex size-6 items-center justify-center rounded-full border bg-background shadow-xs"
            >
              {id === "openai-compatible" ? (
                <BotIcon className="size-3.5" aria-hidden={true} />
              ) : (
                <AiProviderIcon
                  provider={id}
                  className="size-3.5"
                  aria-hidden={true}
                />
              )}
            </figure>
          ))}
        </fieldset>
      </div>
      <button
        type="button"
        onClick={openPairWithAgentModal}
        className="mt-1 text-left text-xs leading-relaxed underline-offset-4 text-link hover:underline"
      >
        Use Claude Code, Codex, OpenCode, or any agent to work with this
        notebook.
      </button>
    </div>
  );
};
