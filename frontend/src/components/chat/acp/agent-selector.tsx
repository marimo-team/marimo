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
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
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
  {
    id: "opencode",
    displayName: "OpenCode",
    iconId: "opencode",
  },
] as const;

interface AgentMenuItemProps {
  agent: (typeof AVAILABLE_AGENTS)[number];
  onSelect: (agentId: ExternalAgentId) => void;
  existingSessions: AgentSession[];
  filename: string | null;
}

const AgentMenuItem = memo<AgentMenuItemProps>(
  ({ agent, onSelect, existingSessions, filename }) => {
    const sessionSupport = getAgentSessionSupport(agent.id);
    const hasExistingSession = existingSessions.some(
      (s) => s.agentId === agent.id,
    );

    const resetSession = sessionSupport === "single" && hasExistingSession;
    const text = resetSession
      ? `Reset ${agent.displayName} session`
      : `New ${agent.displayName} session`;

    if (resetSession) {
      return (
        <DropdownMenuItem
          onClick={() => onSelect(agent.id)}
          className="cursor-pointer"
        >
          <div className="flex items-center w-full">
            <AiProviderIcon provider={agent.iconId} className="h-3 w-3 mr-2" />
            <span>{text}</span>
          </div>
        </DropdownMenuItem>
      );
    }

    return (
      <DropdownMenuSub>
        <DropdownMenuSubTrigger
          showChevron={false}
          className="cursor-pointer"
          onClick={() => onSelect(agent.id)}
        >
          <div className="flex items-center w-full">
            <AiProviderIcon provider={agent.iconId} className="h-3 w-3 mr-2" />
            <span>{text}</span>
          </div>
        </DropdownMenuSubTrigger>
        <DropdownMenuPortal>
          <DropdownMenuSubContent className="w-120">
            <div className="px-2 py-2">
              <div className="text-xs font-medium text-muted-foreground mb-3">
                To start a {agent.displayName} agent, run the following command
                in your terminal.
                <br />
                Note: This must be in the directory{" "}
                <code className="bg-muted font-mono">
                  {Paths.dirname(filename ?? "")}
                </code>
              </div>
              <AgentDocs agents={[agent.id]} showCopy={true} />
            </div>
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
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
              filename={filename}
            />
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  },
);
AgentSelector.displayName = "AgentSelector";
