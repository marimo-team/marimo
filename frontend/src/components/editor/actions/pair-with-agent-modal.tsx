/* Copyright 2026 Marimo. All rights reserved. */

import { CheckIcon, CopyIcon } from "lucide-react";
import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { copyToClipboard } from "@/utils/copy";
import { Events } from "@/utils/events";
import { Tooltip } from "@/components/ui/tooltip";
import { asRemoteURL, useRuntimeManager } from "@/core/runtime/config";
import { API } from "@/core/network/api";
import { getSessionId } from "@/core/kernel/session";
import {
  AGENT_LABELS,
  AGENT_TABS,
  type AgentTab,
  type ConnectionInfo,
  getRawPrompt,
  getTerminalCommand,
  maskToken,
  SKILL_INSTALL,
  TERMINAL_TABS,
} from "./pair-with-agent-commands";

function useAuthToken(): string | null {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    fetch(asRemoteURL("/auth/token").href, {
      headers: API.headers(),
    })
      .then((res) =>
        res.ok ? (res.json() as Promise<{ token: string | null }>) : null,
      )
      .then((data) => setToken(data?.token ?? null))
      .catch(() => setToken(null));
  }, []);
  return token;
}

export const PairWithAgentModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState<AgentTab>("claude");
  const runtimeManager = useRuntimeManager();
  const authToken = useAuthToken();
  const hasToken = Boolean(authToken);
  const connection: ConnectionInfo = {
    url: runtimeManager.httpURL.toString(),
    sessionId: getSessionId(),
  };

  return (
    <DialogContent className="sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>Pair with an agent</DialogTitle>
        <DialogDescription>
          Use an AI coding agent to pair-program on this notebook.{" "}
          <a
            href="https://links.marimo.app/marimo-pair"
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            Learn more
            <span className="sr-only"> about pairing marimo with an agent</span>
          </a>
          .
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-4 py-2">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as AgentTab)}
        >
          <TabsList className="w-full">
            {AGENT_TABS.map((tab) => (
              <TabsTrigger key={tab} value={tab} className="flex-1">
                {AGENT_LABELS[tab]}
              </TabsTrigger>
            ))}
          </TabsList>

          {TERMINAL_TABS.map((tab) => (
            <TabsContent
              key={tab}
              value={tab}
              className="mt-4 flex flex-col gap-4"
            >
              <Step
                index={1}
                title="Install the skill"
                hint="Run once per machine."
              >
                <CommandBlock command={SKILL_INSTALL} />
              </Step>
              <Step index={2} title="Run in your terminal">
                <CommandBlock
                  command={getTerminalCommand(tab, connection, hasToken)}
                />
              </Step>
              {hasToken && authToken && (
                <Step index={3} title="Paste when prompted for a token">
                  <CommandBlock
                    command={authToken}
                    display={maskToken(authToken)}
                  />
                </Step>
              )}
            </TabsContent>
          ))}

          <TabsContent value="prompt" className="mt-4 flex flex-col gap-4">
            <Step
              index={1}
              title="Make sure the marimo-pair skill is available to your agent"
              hint="Skip if your agent already has it."
            >
              <CommandBlock command={SKILL_INSTALL} />
            </Step>
            <Step
              index={2}
              title="Copy this prompt into your agent"
              hint={
                hasToken
                  ? "Includes your auth token — keep it private."
                  : undefined
              }
            >
              <CommandBlock
                command={getRawPrompt(connection, authToken)}
                display={getRawPrompt(
                  connection,
                  authToken ? maskToken(authToken) : null,
                )}
                multiline={true}
              />
            </Step>
          </TabsContent>
        </Tabs>
      </div>

      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </DialogFooter>
    </DialogContent>
  );
};

const Step: React.FC<{
  index: number;
  title: string;
  hint?: string;
  children: React.ReactNode;
}> = ({ index, title, hint, children }) => (
  <div className="flex flex-col gap-2">
    <div className="flex items-baseline gap-2">
      <span className="text-sm font-medium">
        {index}. {title}
      </span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
    {children}
  </div>
);

const CommandBlock: React.FC<{
  command: string;
  display?: string;
  multiline?: boolean;
}> = ({ command, display, multiline = false }) => {
  const [copied, setCopied] = useState(false);

  const copy = Events.stopPropagation(async (e) => {
    e.preventDefault();
    await copyToClipboard(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  });

  if (multiline) {
    return (
      <div className="relative rounded-md bg-muted">
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap wrap-break-word px-3 py-2 pr-10 font-mono text-xs select-all">
          {display ?? command}
        </pre>
        <Tooltip content="Copied!" open={copied}>
          <Button
            onClick={copy}
            size="xs"
            variant="ghost"
            className="absolute right-1 top-1"
          >
            {copied ? (
              <CheckIcon size={14} strokeWidth={1.5} />
            ) : (
              <CopyIcon size={14} strokeWidth={1.5} />
            )}
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 font-mono text-xs">
      <code className="flex-1 select-all wrap-break-word">
        {display ?? command}
      </code>
      <Tooltip content="Copied!" open={copied}>
        <Button onClick={copy} size="xs" variant="ghost">
          {copied ? (
            <CheckIcon size={14} strokeWidth={1.5} />
          ) : (
            <CopyIcon size={14} strokeWidth={1.5} />
          )}
        </Button>
      </Tooltip>
    </div>
  );
};
