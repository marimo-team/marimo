/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { CheckIcon, CopyIcon } from "lucide-react";
import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { runtimeConfigAtom } from "@/core/runtime/config";
import { copyToClipboard } from "@/utils/copy";
import { Events } from "@/utils/events";
import { Tooltip } from "@/components/ui/tooltip";
import type { RuntimeConfig } from "@/core/runtime/types";

type AgentTab = "claude" | "codex" | "opencode";

function buildRemoteUrl(config: RuntimeConfig) {
  const url = new URL(config.url);
  if (config.authToken) {
    url.searchParams.set("auth", config.authToken);
  }
  return url.toString();
}

function getPromptCommand(agent: AgentTab, remoteUrl: string): string {
  const command = import.meta.env.DEV ? "uv run marimo" : "uvx marimo@latest";
  const base = `${command} pair prompt --url '${remoteUrl}'`;
  switch (agent) {
    case "claude":
      return `claude "$(${base} --claude)"`;
    case "codex":
      return `codex "$(${base} --codex)"`;
    case "opencode":
      return `opencode "$(${base} --opencode)"`;
  }
}

const SKILL_INSTALL = "npx skills add marimo-team/marimo-pair";

export const PairWithAgentModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState<AgentTab>("claude");
  const runtimeConfig = useAtomValue(runtimeConfigAtom);
  const remoteUrl = buildRemoteUrl(runtimeConfig);
  const promptCommand = getPromptCommand(activeTab, remoteUrl);

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
      </div>

      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </DialogFooter>
    </DialogContent>
  );
};

const CommandBlock: React.FC<{ command: string }> = ({ command }) => {
  const [copied, setCopied] = useState(false);

  const copy = Events.stopPropagation(async (e) => {
    e.preventDefault();
    await copyToClipboard(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  });

  return (
    <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 font-mono text-xs">
      <code className="flex-1 select-all break-words">{command}</code>
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
