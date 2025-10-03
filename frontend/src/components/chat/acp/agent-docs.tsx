/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { TerminalIcon, TerminalSquareIcon } from "lucide-react";
import { memo } from "react";
import { AiProviderIcon } from "@/components/ai/ai-provider-icon";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { useTerminalCommands } from "@/components/terminal/hooks";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { cn } from "@/utils/cn";
import {
  type ExternalAgentId,
  getAgentConnectionCommand,
  getAgentDisplayName,
  getAllAgentIds,
} from "./state";

interface AgentDocItemProps {
  agentId: ExternalAgentId;
  showCopy?: boolean;
  className?: string;
}

const AgentDocItem = memo<AgentDocItemProps>(
  ({ agentId, showCopy = true, className }) => {
    const command = getAgentConnectionCommand(agentId);
    const displayName = getAgentDisplayName(agentId);
    const capabilities = useAtomValue(capabilitiesAtom);
    const { sendCommand } = useTerminalCommands();

    const handleSendToTerminal = () => {
      sendCommand(command);
    };

    return (
      <div className={cn("space-y-2", className)}>
        <div className="flex items-center gap-2">
          <AiProviderIcon provider={agentId} className="h-4 w-4" />
          <span className="font-medium text-sm">{displayName}</span>
        </div>
        <div className="bg-muted/50 rounded-md p-2 border">
          <div className="flex items-start gap-2 text-xs">
            <TerminalIcon className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
            <code className="text-xs font-mono break-words flex-1 whitespace-pre-wrap">
              {command}
            </code>
            <div className="flex items-center gap-1 flex-shrink-0">
              {showCopy && (
                <Button size="xs" variant="outline" className="border">
                  <CopyClipboardIcon value={command} className="h-3 w-3" />
                </Button>
              )}
              {capabilities.terminal && (
                <Tooltip content="Run in terminal" delayDuration={100}>
                  <Button
                    onClick={handleSendToTerminal}
                    title="Send to terminal"
                    size="xs"
                    variant="outline"
                  >
                    <TerminalSquareIcon className="h-3 w-3" />
                  </Button>
                </Tooltip>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  },
);
AgentDocItem.displayName = "AgentDocItem";

interface AgentDocsProps {
  title?: string;
  description?: React.ReactNode;
  agents?: ExternalAgentId[];
  showCopy?: boolean;
  className?: string;
}

export const AgentDocs = memo<AgentDocsProps>(
  ({
    title,
    description,
    agents = getAllAgentIds(),
    showCopy = true,
    className,
  }) => (
    <div className={cn("space-y-4", className)}>
      <div className="space-y-2">
        <h3 className="font-medium text-sm">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="space-y-3">
        {agents.map((agentId) => (
          <AgentDocItem key={agentId} agentId={agentId} showCopy={showCopy} />
        ))}
      </div>
    </div>
  ),
);
AgentDocs.displayName = "AgentDocs";
