/* Copyright 2025 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { ChevronDownIcon, PlusIcon } from "lucide-react";
import React, { memo, useState } from "react";
import useEvent from "react-use-event-hook";
import { AiProviderIcon } from "@/components/ai/ai-provider-icon";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/cn";
import {
  activeSessionAtom,
  addSession,
  agentSessionStateAtom,
  createSession,
  type ExternalAgentId,
} from "./state";

interface AgentSelectorProps {
  onSessionCreated?: (agentId: ExternalAgentId) => void;
  className?: string;
}

const AVAILABLE_AGENTS = [
  {
    id: "claude",
    displayName: "Claude",
    iconId: "anthropic",
  },
  {
    id: "gemini",
    displayName: "Gemini",
    iconId: "google",
  },
] as const;

interface AgentMenuItemProps {
  agent: (typeof AVAILABLE_AGENTS)[number];
  onSelect: (agentId: ExternalAgentId) => void;
}

const AgentMenuItem = memo<AgentMenuItemProps>(({ agent, onSelect }) => (
  <DropdownMenuItem
    onClick={() => onSelect(agent.id)}
    className="cursor-pointer"
  >
    <div className="flex items-center w-full">
      <AiProviderIcon provider={agent.iconId} className="h-3 w-3 mr-2" />
      <span>New {agent.displayName} session</span>
    </div>
  </DropdownMenuItem>
));
AgentMenuItem.displayName = "AgentMenuItem";

export const AgentSelector: React.FC<AgentSelectorProps> = memo(
  ({ onSessionCreated, className }) => {
    const [sessionState, setSessionState] = useAtom(agentSessionStateAtom);
    const [, setActiveSession] = useAtom(activeSessionAtom);
    const [isOpen, setIsOpen] = useState(false);

    const handleCreateSession = useEvent(async (agentId: ExternalAgentId) => {
      const newSession = createSession(agentId);
      const newState = addSession(sessionState, newSession);

      setSessionState(newState);
      setActiveSession(newSession.id);
      setIsOpen(false);

      onSessionCreated?.(agentId);
    });

    return (
      <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-6 gap-1 px-2 text-xs bg-muted/30 hover:bg-muted/50 border border-border border-y-0 rounded-none focus-visible:ring-0",
              className,
            )}
          >
            <PlusIcon className="h-3 w-3" />
            <span>New Session</span>
            <ChevronDownIcon className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {AVAILABLE_AGENTS.map((agent) => (
            <AgentMenuItem
              key={agent.id}
              agent={agent}
              onSelect={handleCreateSession}
            />
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  },
);
AgentSelector.displayName = "AgentSelector";
