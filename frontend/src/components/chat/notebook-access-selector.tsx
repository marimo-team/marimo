/* Copyright 2026 Marimo. All rights reserved. */

import {
  EyeIcon,
  type LucideIcon,
  PencilIcon,
  TerminalIcon,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
} from "@/components/ui/select";
import type { CopilotMode } from "@/core/config/config-schema";

const ACCESS_LEVELS = {
  ask: {
    label: "Read only",
    description: "Read notebook code, outputs, and variable previews.",
    Icon: EyeIcon,
  },
  agent: {
    label: "Suggest edits",
    description: "Read the notebook and propose cell changes for review.",
    Icon: PencilIcon,
  },
  code_mode: {
    label: "Full access",
    description: "Read, edit, and run cells, with Python scratchpad access.",
    Icon: TerminalIcon,
  },
} satisfies Record<
  Exclude<CopilotMode, "manual">,
  { label: string; description: string; Icon: LucideIcon }
>;

const ACCESS_MODES = ["ask", "agent", "code_mode"] as const;

interface NotebookAccessSelectorProps {
  value: CopilotMode;
  onValueChange: (value: CopilotMode) => void;
}

export const NotebookAccessSelector = ({
  value,
  onValueChange,
}: NotebookAccessSelectorProps) => {
  const mode = value === "manual" ? "ask" : value;
  const selected = ACCESS_LEVELS[mode];

  return (
    <Select
      value={mode}
      onValueChange={(value) => {
        const mode = ACCESS_MODES.find((mode) => mode === value);
        if (mode) {
          onValueChange(mode);
        }
      }}
    >
      <SelectTrigger
        aria-label={`Notebook access: ${selected.label}`}
        title={`Notebook access: ${selected.description}`}
        className="chat-control chat-selector h-6 text-xs border-border py-0 px-2 gap-1.5 shrink-0"
      >
        <selected.Icon className="h-3 w-3" />
        <span className="text-nowrap">{selected.label}</span>
      </SelectTrigger>
      <SelectContent className="max-w-[calc(100vw-2rem)]">
        <SelectGroup>
          <SelectLabel className="text-xs uppercase tracking-wider text-muted-foreground/70 font-medium">
            Notebook access
          </SelectLabel>
          {ACCESS_MODES.map((mode) => {
            const { label, description, Icon } = ACCESS_LEVELS[mode];
            return (
              <SelectItem
                key={mode}
                value={mode}
                textValue={label}
                className="text-xs py-1"
              >
                <div className="flex items-start gap-2.5">
                  <Icon className="h-3 w-3 mt-1 shrink-0 text-muted-foreground" />
                  <div className="flex flex-col gap-0.5">
                    <span className="font-semibold">{label}</span>
                    <span className="text-muted-foreground">{description}</span>
                  </div>
                </div>
              </SelectItem>
            );
          })}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
};
