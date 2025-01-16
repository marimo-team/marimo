/* Copyright 2024 Marimo. All rights reserved. */

import { EditorView } from '@codemirror/view';
import { CompletionContext, CompletionResult, Completion } from '@codemirror/autocomplete';
import { Logger } from '@/utils/Logger';

interface MCPServer {
  name: string;
  tools: Array<{ name: string; description: string }>;
  resources: Array<{ name: string; description: string }>;
  prompts: Array<{ name: string; description: string }>;
}

interface ServerResponse {
  servers: MCPServer[];
}

export async function mcpCompletions(
  context: CompletionContext,
  serverName: string | null
): Promise<CompletionResult | null> {
  if (!serverName) {
    return null;
  }

  const word = context.matchBefore(/[!/@][^\s()]*$/);
  if (!word) {
    return null;
  }

  const trigger = word.text[0];
  if (!['@', '!', '/'].includes(trigger)) {
    return null;
  }

  try {
    const response = await fetch('/api/mcp/servers');
    if (!response.ok) {
      return null;
    }

    const { servers }: ServerResponse = await response.json();
    const server = servers.find((s) => s.name === serverName);
    if (!server) {
      return null;
    }

    let completions: Array<{ label: string; detail: string }> = [];
    const prefix = word.text.slice(1);

    switch (trigger) {
      case '@':
        completions = server.resources.map((r) => ({
          label: r.name,
          detail: r.description,
        }));
        break;
      case '!':
        completions = server.tools.map((t) => ({
          label: t.name,
          detail: t.description,
        }));
        break;
      case '/':
        completions = server.prompts.map((p) => ({
          label: p.name,
          detail: p.description,
        }));
        break;
    }

    if (prefix) {
      completions = completions.filter((c) =>
        c.label.toLowerCase().includes(prefix.toLowerCase())
      );
    }

    return {
      from: word.from + 1, // +1 to exclude the trigger character
      options: completions.map((c) => ({
        label: c.label,
        detail: c.detail,
        apply: (view: EditorView, completion: Completion, from: number, to: number) => {
          const suffix = '()';
          view.dispatch({
            changes: {
              from,
              to,
              insert: `${completion.label}${suffix}`,
            },
            selection: { anchor: from + completion.label.length + 1 },
          });
        },
      })),
    };
  } catch (error) {
    Logger.error('Error fetching MCP completions:', error);
    return null;
  }
} 
