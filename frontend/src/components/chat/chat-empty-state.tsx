/* Copyright 2026 Marimo. All rights reserved. */

import { PlugIcon } from "lucide-react";
import { usePairWithAgentModal } from "@/components/editor/actions/pair-with-agent";
import { MarimoIcon } from "@/components/icons/marimo-icons";
import { Button } from "@/components/ui/button";
import { isWasm } from "@/core/wasm/utils";

const STARTER_PROMPTS = [
  "Explain this notebook",
  "Help me visualize my data",
  "Suggest improvements",
];

interface ChatEmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export const ChatEmptyState = ({ onSelectPrompt }: ChatEmptyStateProps) => {
  const openPairWithAgentModal = usePairWithAgentModal();

  return (
    <div className="flex flex-1 flex-col justify-center pb-12">
      <div className="mx-auto flex w-full max-w-xs flex-col items-center gap-5 px-3 py-6">
        <MarimoIcon size={40} stroke="#1c7361" />
        <h2 className="text-center text-base font-medium leading-6 text-foreground">
          What would you like to do?
        </h2>
        <div className="flex w-full flex-col gap-2">
          {STARTER_PROMPTS.map((prompt) => (
            <Button
              key={prompt}
              variant="outline"
              className="h-auto min-h-9 justify-start border-border px-3 py-2 text-left text-xs font-normal shadow-none whitespace-normal"
              onClick={() => onSelectPrompt(prompt)}
            >
              {prompt}
            </Button>
          ))}
        </div>
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
