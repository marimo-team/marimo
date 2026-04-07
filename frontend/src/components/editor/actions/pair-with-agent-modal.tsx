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
import { assertNever } from "@/utils/assertNever";
import { asRemoteURL, useRuntimeManager } from "@/core/runtime/config";
import { API } from "@/core/network/api";

type AgentTab = "claude" | "codex" | "opencode";

function getMarimoCommand(): string {
  return import.meta.env.DEV ? "uv run marimo" : "uvx marimo@latest";
}

function getPromptCommand(
  agent: AgentTab,
  url: string,
  withToken: boolean,
): string {
  const tokenFlag = withToken ? " --with-token" : "";
  const base = `${getMarimoCommand()} pair prompt --url '${url}'${tokenFlag}`;
  switch (agent) {
    case "claude":
      return `claude "$(${base} --claude)"`;
    case "codex":
      return `codex "$(${base} --codex)"`;
    case "opencode":
      return `opencode "$(${base} --opencode)"`;
    default:
      assertNever(agent);
  }
}

function maskToken(token: string): string {
  if (token.length <= 4) {
    return "****";
  }
  return `${"*".repeat(Math.min(token.length - 4, 8))}${token.slice(-4)}`;
}

const SKILL_INSTALL = "npx skills add marimo-team/marimo-pair";

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
  const remoteUrl = runtimeManager.httpURL.toString();
  const promptCommand = getPromptCommand(activeTab, remoteUrl, hasToken);

  return (
    <DialogContent className="sm:max-w-lg">
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
          </a>
          .
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-4 py-2">
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium">1. Install the skill</span>
          <CommandBlock command={SKILL_INSTALL} />
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium">2. Run in your terminal</span>
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as AgentTab)}
          >
            <TabsList className="w-full">
              <TabsTrigger value="claude" className="flex-1">
                Claude
              </TabsTrigger>
              <TabsTrigger value="codex" className="flex-1">
                Codex
              </TabsTrigger>
              <TabsTrigger value="opencode" className="flex-1">
                OpenCode
              </TabsTrigger>
            </TabsList>

            <TabsContent value="claude" className="mt-3">
              <CommandBlock command={promptCommand} />
            </TabsContent>
            <TabsContent value="codex" className="mt-3">
              <CommandBlock command={promptCommand} />
            </TabsContent>
            <TabsContent value="opencode" className="mt-3">
              <CommandBlock command={promptCommand} />
            </TabsContent>
          </Tabs>
        </div>

        {hasToken && authToken && (
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">
              3. Paste when prompted for token
            </span>
            <CommandBlock command={authToken} display={maskToken(authToken)} />
          </div>
        )}
      </div>

      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </DialogFooter>
    </DialogContent>
  );
};

const CommandBlock: React.FC<{ command: string; display?: string }> = ({
  command,
  display,
}) => {
  const [copied, setCopied] = useState(false);

  const copy = Events.stopPropagation(async (e) => {
    e.preventDefault();
    await copyToClipboard(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  });

  return (
    <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 font-mono text-xs">
      <code className="flex-1 select-all break-words">
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
