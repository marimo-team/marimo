/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom, useSetAtom } from "jotai";
import { ChevronDownIcon } from "lucide-react";
import React, { memo, useState } from "react";
import useEvent from "react-use-event-hook";
import { AiProviderIcon } from "@/components/ai/ai-provider-icon";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useFilename } from "@/core/saving/filename";
import { cn } from "@/utils/cn";
import { Paths } from "@/utils/paths";
import { AgentDocs } from "./agent-docs";
import {
  type AgentSession,
  addSession,
  agentSessionStateAtom,
  type ExternalAgentId,
  getAgentSessionSupport,
  selectedTabAtom,
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
  {
    id: "codex",
    displayName: "Codex",
    iconId: "openai",
  },
] as const;

interface AgentMenuItemProps {
  agent: (typeof AVAILABLE_AGENTS)[number];
  onSelect: (agentId: ExternalAgentId) => void;
  existingSessions: AgentSession[];
}

const AgentMenuItem = memo<AgentMenuItemProps>(
  ({ agent, onSelect, existingSessions }) => {
    const sessionSupport = getAgentSessionSupport(agent.id);
    const hasExistingSession = existingSessions.some(
      (s) => s.agentId === agent.id,
    );

    const getText = () => {
      if (sessionSupport === "single" && hasExistingSession) {
        return `Reset ${agent.displayName} session`;
      }
      return `New ${agent.displayName} session`;
    };

    return (
      <DropdownMenuItem
        onClick={() => onSelect(agent.id)}
        className="cursor-pointer"
      >
        <div className="flex items-center w-full">
          <AiProviderIcon provider={agent.iconId} className="h-3 w-3 mr-2" />
          <span>{getText()}</span>
        </div>
      </DropdownMenuItem>
    );
  },
);
AgentMenuItem.displayName = "AgentMenuItem";

export const AgentSelector: React.FC<AgentSelectorProps> = memo(
  ({ onSessionCreated, className }) => {
    const filename = useFilename();
    const [sessionState, setSessionState] = useAtom(agentSessionStateAtom);
    const setActiveTab = useSetAtom(selectedTabAtom);
    const [isOpen, setIsOpen] = useState(false);

    const handleCreateSession = useEvent(async (agentId: ExternalAgentId) => {
      const newState = addSession(sessionState, {
        agentId,
      });

      setSessionState(newState);
      setActiveTab(newState.activeTabId);
      setIsOpen(false);

      onSessionCreated?.(agentId);
    });

    return (
      <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild={true}>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-6 gap-1 px-2 text-xs bg-muted/30 hover:bg-muted/50 border border-border border-y-0 rounded-none focus-visible:ring-0",
              className,
            )}
          >
            <span>New session</span>
            <ChevronDownIcon className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-fit">
          {AVAILABLE_AGENTS.map((agent) => (
            <AgentMenuItem
              key={agent.id}
              agent={agent}
              onSelect={handleCreateSession}
              existingSessions={sessionState.sessions}
            />
          ))}
          <DropdownMenuSeparator />
          <div className="px-2 py-2">
            <div className="text-xs font-medium text-muted-foreground mb-3">
              To start an external agent, run the following command in your
              terminal.
              <br />
              Note: This must be in the directory{" "}
              {Paths.dirname(filename ?? "")}
            </div>
            <AgentDocs
              agents={AVAILABLE_AGENTS.map((agent) => agent.id)}
              showCopy={true}
            />
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  },
);
AgentSelector.displayName = "AgentSelector";
