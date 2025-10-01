/* Copyright 2024 Marimo. All rights reserved. */

import { CheckSquareIcon } from "lucide-react";
import React from "react";
import type { UseFormReturn } from "react-hook-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FormField, FormItem } from "@/components/ui/form";
import type { UserConfig } from "@/core/config/config-schema";
import { Button } from "../ui/button";
import { Kbd } from "../ui/kbd";
import { SettingSubtitle } from "./common";
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
    title: "marimo (docs)",
    description: "Access marimo documentation",
  },
  {
    id: "context7",
    title: "Context7",
    description: "Connect to Context7 MCP server",
  },
];

export const MCPConfig: React.FC<MCPConfigProps> = ({ form, onSubmit }) => {
  const { handleClick } = useOpenSettingsToTab();

  return (
    <div className="flex flex-col gap-4">
      <SettingSubtitle>MCP Servers</SettingSubtitle>
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
          Optional Features
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
            <FormItem>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {PRESET_CONFIGS.map((config) => {
                  const isChecked = presets.includes(config.id);

                  return (
                    <Card
                      key={config.id}
                      className={`cursor-pointer transition-all ${
                        isChecked
                          ? "border-[var(--blue-9)] bg-[var(--blue-2)]"
                          : "hover:border-[var(--blue-7)]"
                      }`}
                      onClick={() => togglePreset(config.id)}
                    >
                      <CardHeader>
                        <div className="flex items-start justify-between">
                          <CardTitle className="text-base">
                            {config.title}
                          </CardTitle>
                          <span
                            className={`h-5 w-5 flex items-center justify-center rounded border ${
                              isChecked
                                ? "border-[var(--blue-7)] bg-[var(--blue-7)] text-foreground"
                                : "border-muted bg-background text-muted-foreground"
                            }`}
                          >
                            {isChecked ? <CheckSquareIcon /> : null}
                          </span>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <CardDescription>{config.description}</CardDescription>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </FormItem>
          );
        }}
      />
    </div>
  );
};
