/* Copyright 2026 Marimo. All rights reserved. */

import type { ChatAddToolApproveResponseFunction } from "ai";
import { ShieldQuestionIcon } from "lucide-react";
import React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { formatToolName, type ToolApproval } from "./shared";
import { ToolArgsRenderer } from "./tool-args";

interface ToolApprovalCardProps {
  toolName: string;
  input: unknown;
  approval: ToolApproval;
  onApprove: ChatAddToolApproveResponseFunction;
  className?: string;
}

export const ToolApprovalCard: React.FC<ToolApprovalCardProps> = ({
  toolName,
  input,
  approval,
  onApprove,
  className,
}) => {
  return (
    <div
      className={cn(
        "rounded-md border border-(--amber-6) bg-(--amber-2) p-3 space-y-3",
        className,
      )}
      role="alertdialog"
      aria-label={`Approval required for ${formatToolName(toolName)}`}
    >
      <div className="flex items-start gap-2">
        <ShieldQuestionIcon className="h-4 w-4 text-(--amber-11) mt-0.5 shrink-0" />
        <div className="text-xs text-(--amber-11) leading-relaxed">
          <span className="font-semibold">Approval required:</span>{" "}
          <code className="font-mono">{formatToolName(toolName)}</code>
        </div>
      </div>

      <ToolArgsRenderer input={input} />

      <div className="flex items-center justify-end gap-2">
        <Button
          size="xs"
          variant="outline"
          onClick={() => onApprove({ id: approval.id, approved: false })}
        >
          Deny
        </Button>
        <Button
          size="xs"
          onClick={() => onApprove({ id: approval.id, approved: true })}
        >
          Approve
        </Button>
      </div>
    </div>
  );
};
