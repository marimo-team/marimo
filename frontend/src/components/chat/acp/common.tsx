/* Copyright 2024 Marimo. All rights reserved. */

import type { RequestPermissionResponse } from "@zed-industries/agent-client-protocol";
import {
  CheckCircleIcon,
  Loader2,
  PlugIcon,
  ShieldCheckIcon,
  WifiIcon,
  WifiOffIcon,
  XCircleIcon,
} from "lucide-react";
import React, { memo } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { ToolBodyBlock } from "./blocks";
import type { AgentPendingPermission } from "./types";

interface SimpleAccordionProps {
  title: string | React.ReactNode;
  children: React.ReactNode | string;
  status?: "loading" | "error" | "success";
  index?: number;
  defaultIcon?: React.ReactNode;
}

export const SimpleAccordion: React.FC<SimpleAccordionProps> = ({
  title,
  children,
  status,
  index = 0,
  defaultIcon,
}) => {
  const getStatusIcon = () => {
    switch (status) {
      case "loading":
        return <Loader2 className="h-3 w-3 animate-spin" />;
      case "error":
        return <XCircleIcon className="h-3 w-3 text-destructive" />;
      case "success":
        return <CheckCircleIcon className="h-3 w-3 text-[var(--blue-9)]" />;
      default:
        return defaultIcon;
    }
  };

  return (
    <Accordion
      key={`tool-${index}`}
      type="single"
      collapsible={true}
      className="w-full"
    >
      <AccordionItem value="tool-call" className="border-0">
        <AccordionTrigger
          className={cn(
            "py-1 text-xs border-border shadow-none! ring-0! bg-muted hover:bg-muted/30 px-2 gap-1 rounded-sm [&[data-state=open]>svg]:rotate-180",
            status === "error" && "text-destructive/80",
            status === "success" && "text-[var(--blue-8)]",
          )}
        >
          <span className="flex items-center gap-1">
            {getStatusIcon()}
            <code className="font-mono text-xs truncate">{title}</code>
          </span>
        </AccordionTrigger>
        <AccordionContent className="p-2">
          <div className="space-y-3 max-h-64 overflow-y-auto scrollbar-thin">
            {status !== "error" && (
              <div className="text-xs font-medium text-muted-foreground mb-1">
                {children}
              </div>
            )}

            {status === "error" && (
              <div className="bg-destructive/10 border border-destructive/20 rounded-md p-3 text-xs text-destructive">
                {children}
              </div>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};

interface ConnectionStatusProps {
  status: string;
  className?: string;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = memo(
  ({ status, className }) => {
    const getStatusConfig = () => {
      switch (status) {
        case "connected":
          return {
            icon: <WifiIcon className="h-3 w-3" />,
            label: "Connected",
            variant: "default" as const,
            className:
              "bg-[var(--blue-3)] text-[var(--blue-11)] border-[var(--blue-5)]",
          };
        case "connecting":
          return {
            icon: <PlugIcon className="h-3 w-3 animate-pulse" />,
            label: "Connecting",
            variant: "secondary" as const,
            className:
              "bg-[var(--yellow-3)] text-[var(--yellow-11)] border-[var(--yellow-5)]",
          };
        case "disconnected":
          return {
            icon: <WifiOffIcon className="h-3 w-3" />,
            label: "Disconnected",
            variant: "outline" as const,
            className:
              "bg-[var(--red-3)] text-[var(--red-11)] border-[var(--red-5)]",
          };
        default:
          return {
            icon: <WifiOffIcon className="h-3 w-3" />,
            label: status || "Unknown",
            variant: "outline" as const,
            className:
              "bg-[var(--gray-3)] text-[var(--gray-11)] border-[var(--gray-5)]",
          };
      }
    };

    const config = getStatusConfig();

    return (
      <Badge
        variant={config.variant}
        className={cn(config.className, className)}
      >
        {config.icon}
        <span className="ml-1 text-xs font-medium">{config.label}</span>
      </Badge>
    );
  },
);
ConnectionStatus.displayName = "ConnectionStatus";

interface PermissionRequestProps {
  permission: NonNullable<AgentPendingPermission>;
  onResolve: (option: RequestPermissionResponse) => void;
}

export const PermissionRequest: React.FC<PermissionRequestProps> = memo(
  ({ permission, onResolve }) => {
    return (
      <div className="border border-[var(--amber-8)] bg-[var(--amber-2)] rounded-lg p-2">
        <div className="flex items-center gap-2 mb-3">
          <ShieldCheckIcon className="h-4 w-4 text-[var(--amber-11)]" />
          <h3 className="text-sm font-medium text-[var(--amber-11)]">
            Permission Request
          </h3>
        </div>
        <p className="text-sm text-[var(--amber-11)] mb-3">
          The AI agent is requesting permission to proceed:
        </p>
        <ToolBodyBlock data={permission.toolCall} />
        <div className="flex gap-2">
          {permission.options.map((option) => (
            <Button
              key={option.optionId}
              size="xs"
              variant="text"
              className={
                option.kind.startsWith("allow")
                  ? "text-[var(--blue-10)]"
                  : "text-[var(--red-10)]"
              }
              onClick={() =>
                onResolve({
                  outcome: {
                    outcome: "selected",
                    optionId: option.optionId,
                  },
                })
              }
            >
              {option.kind.startsWith("allow") && (
                <CheckCircleIcon className="h-3 w-3 mr-1" />
              )}
              {option.kind.startsWith("reject") && (
                <XCircleIcon className="h-3 w-3 mr-1" />
              )}
              {option.name}
            </Button>
          ))}
        </div>
      </div>
    );
  },
);
PermissionRequest.displayName = "PermissionRequest";
