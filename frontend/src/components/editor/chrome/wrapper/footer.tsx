/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import { cn } from "@/utils/cn";
import { useChromeActions, useChromeState } from "../state";
import { Tooltip } from "@/components/ui/tooltip";
import { useAtomValue } from "jotai";
import { cellErrorCount } from "@/core/cells/cells";
import { PANEL_ICONS, PanelType } from "../types";
import { MachineStats } from "./machine-stats";
import { useUserConfig } from "@/core/config/config";
import { ZapIcon, ZapOffIcon } from "lucide-react";
import { saveUserConfig } from "@/core/network/requests";
import { UserConfig } from "@/core/config/config-schema";

export const Footer: React.FC = () => {
  const { selectedPanel } = useChromeState();
  const { openApplication } = useChromeActions();
  const [config, setConfig] = useUserConfig();
  const errorCount = useAtomValue(cellErrorCount);

  const renderIcon = (type: PanelType, className?: string) => {
    const Icon = PANEL_ICONS[type];
    return <Icon className={cn("h-5 w-5", className)} />;
  };

  return (
    <footer className="h-10 py-2 bg-background flex items-center text-muted-foreground text-md pl-1 pr-4 border-t border-border select-none no-print text-sm shadow-[0_0_4px_1px_rgba(0,0,0,0.1)] z-50 divide-x">
      <FooterItem
        tooltip="View errors"
        selected={selectedPanel === "errors"}
        onClick={() => openApplication("errors")}
      >
        {renderIcon("errors", errorCount > 0 ? "text-destructive" : "")}
        <span className="ml-1 font-mono mt-[0.125rem]">{errorCount}</span>
      </FooterItem>

      <FooterItem
        tooltip={
          config.runtime.auto_instantiate
            ? "Disable autorun on startup"
            : "Enable autorun on startup"
        }
        selected={false}
        onClick={async () => {
          const newConfig = {
            ...config,
            runtime: {
              ...config.runtime,
              auto_instantiate: !config.runtime.auto_instantiate,
            },
          };
          await saveUserConfig({ config: newConfig }).then(() =>
            setConfig(newConfig),
          );
        }}
      >
        <div className="font-prose text-sm flex items-center gap-1">
          <span>on startup: </span>
          {config.runtime.auto_instantiate ? (
            <ZapIcon size={14} />
          ) : (
            <ZapOffIcon size={16} />
          )}
          <span>{config.runtime.auto_instantiate ? "autorun" : "lazy"}</span>
        </div>
      </FooterItem>

      <FooterItem
        tooltip={
          config.runtime.on_cell_change === "autorun"
            ? "Disable autorun"
            : "Enable autorun"
        }
        selected={false}
        onClick={async () => {
          const newConfig: UserConfig = {
            ...config,
            runtime: {
              ...config.runtime,
              on_cell_change:
                config.runtime.on_cell_change === "autorun"
                  ? "lazy"
                  : "autorun",
            },
          };
          await saveUserConfig({ config: newConfig }).then(() =>
            setConfig(newConfig),
          );
        }}
      >
        <div className="font-prose text-sm flex items-center gap-1">
          <span>on cell change: </span>
          {config.runtime.on_cell_change === "autorun" ? (
            <ZapIcon size={14} />
          ) : (
            <ZapOffIcon size={16} />
          )}
          <span>{config.runtime.on_cell_change}</span>
        </div>
      </FooterItem>

      <div className="mx-auto" />

      <MachineStats />
    </footer>
  );
};

const FooterItem: React.FC<
  PropsWithChildren<
    {
      selected: boolean;
      tooltip: React.ReactNode;
    } & React.HTMLAttributes<HTMLDivElement>
  >
> = ({ children, tooltip, selected, className, ...rest }) => {
  return (
    <Tooltip content={tooltip} side="top" delayDuration={200}>
      <div
        className={cn(
          "h-full flex items-center p-2 text-sm mx-[1px] shadow-inset font-mono cursor-pointer rounded",
          !selected && "hover:bg-[var(--sage-3)]",
          selected && "bg-[var(--sage-4)]",
          className,
        )}
        {...rest}
      >
        {children}
      </div>
    </Tooltip>
  );
};
