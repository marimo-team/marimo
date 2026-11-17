/* Copyright 2026 Marimo. All rights reserved. */

import { Loader2, RefreshCwIcon } from "lucide-react";
import React from "react";
import type { UseFormReturn } from "react-hook-form";
import { Checkbox } from "@/components/ui/checkbox";
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form";
import type { UserConfig } from "@/core/config/config-schema";
import { useMCPRefresh, useMCPStatus } from "../mcp/hooks";
import { McpStatusText } from "../mcp/mcp-status-indicator";
import { Button } from "../ui/button";
import { Kbd } from "../ui/kbd";
import { formItemClasses, SettingSubtitle } from "./common";
import { useOpenSettingsToTab } from "./state";

interface MCPConfigProps {
  form: UseFormReturn<UserConfig>;
  onSubmit: (values: UserConfig) => void;
}

type MCPPreset = "marimo" | "context7";

interface PresetConfig {
  id: MCPPreset;
  title: string;
  description: string;
}

const PRESET_CONFIGS: PresetConfig[] = [
  {
    id: "marimo",
    title: "marimo documentation",
    description: "Let the AI assistant look up marimo documentation.",
  },
  {
    id: "context7",
    title: "Context7",
    description:
      "Let the AI assistant look up current documentation and code examples for third-party libraries using Context7.",
  },
];

export const MCPConfig: React.FC<MCPConfigProps> = ({ form, onSubmit }) => {
  const { handleClick } = useOpenSettingsToTab();
  const { data: status, refetch, isFetching } = useMCPStatus();
  const { refresh, isRefreshing } = useMCPRefresh();

  const handleRefresh = async () => {
    await refresh();
    refetch();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <SettingSubtitle>MCP servers</SettingSubtitle>
        <div className="flex items-center gap-2">
          {status && <McpStatusText status={status.status} />}
          <Button
            variant="outline"
            size="xs"
            aria-label="Refresh MCP servers"
            onClick={handleRefresh}
            disabled={isRefreshing || isFetching}
          >
            {isRefreshing || isFetching ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCwIcon className="h-3 w-3" />
            )}
          </Button>
        </div>
      </div>
      {status?.error && (
        <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/20 p-2 rounded">
          {status.error}
        </div>
      )}
      {status?.servers && (
        <div className="text-xs text-muted-foreground">
          {Object.entries(status.servers).map(([server, status]) => (
            <div key={server}>
              {server}: <McpStatusText status={status} />
            </div>
          ))}
        </div>
      )}
      <p className="text-sm text-muted-foreground">
        Enable Model Context Protocol (MCP) servers to provide additional
        capabilities and data sources for AI features.
      </p>
      <p className="text-sm text-muted-foreground">
        This feature requires the <Kbd className="inline">marimo[mcp]</Kbd>{" "}
        package. See{" "}
        <Button
          variant="link"
          onClick={() => handleClick("optionalDeps")}
          size="xs"
        >
          Optional features
        </Button>{" "}
        for more details.
      </p>

      <FormField
        control={form.control}
        name="mcp.presets"
        render={({ field }) => {
          const presets = field.value || [];

          const togglePreset = (preset: MCPPreset) => {
            const newPresets = presets.includes(preset)
              ? presets.filter((p: string) => p !== preset)
              : [...presets, preset];
            field.onChange(newPresets);
            onSubmit(form.getValues());
          };

          return (
            <div className="flex flex-col gap-6">
              {PRESET_CONFIGS.map((config) => (
                <FormItem key={config.id} className={formItemClasses}>
                  <FormLabel>{config.title}</FormLabel>
                  <FormControl>
                    <Checkbox
                      checked={presets.includes(config.id)}
                      onCheckedChange={() => togglePreset(config.id)}
                    />
                  </FormControl>
                  <FormDescription>{config.description}</FormDescription>
                </FormItem>
              ))}
            </div>
          );
        }}
      />
    </div>
  );
};
