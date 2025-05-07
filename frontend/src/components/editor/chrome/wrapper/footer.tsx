/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import { cn } from "@/utils/cn";
import { useChromeActions, useChromeState } from "../state";
import { Tooltip } from "@/components/ui/tooltip";
import { useAtomValue } from "jotai";
import { cellErrorCount } from "@/core/cells/cells";
import { type PanelDescriptor, PANELS } from "../types";
import { MachineStats } from "./footer-items/machine-stats";
import { useResolvedMarimoConfig } from "@/core/config/config";
import {
  PowerOffIcon,
  TerminalSquareIcon,
  ZapIcon,
  ZapOffIcon,
} from "lucide-react";
import { saveUserConfig } from "@/core/network/requests";
import type { UserConfig } from "@/core/config/config-schema";
import { ShowInKioskMode } from "../../kiosk-mode";
import { invariant } from "@/utils/invariant";
import { IfCapability } from "@/core/config/if-capability";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDownIcon } from "lucide-react";
import { FooterItem } from "./footer-item";
import { useHotkey } from "@/hooks/useHotkey";
import { isWasm } from "@/core/wasm/utils";
import { AIStatusIcon } from "./footer-items/ai-status";
import { BackendConnection } from "./footer-items/backend-status";
import { CopilotStatusIcon } from "./footer-items/copilot-status";
import { RTCStatus } from "./footer-items/rtc-status";

export const Footer: React.FC = () => {
  const { selectedPanel, isTerminalOpen } = useChromeState();
  const { toggleApplication, toggleTerminal } = useChromeActions();
  const [config, setConfig] = useResolvedMarimoConfig();
  const errorCount = useAtomValue(cellErrorCount);

  const renderIcon = ({ Icon }: PanelDescriptor, className?: string) => {
    return <Icon className={cn("h-5 w-5", className)} />;
  };

  const errorPanel = PANELS.find((p) => p.type === "errors");
  invariant(errorPanel, "Error panel not found");

  useHotkey("global.toggleTerminal", () => {
    toggleTerminal();
  });

  return (
    <footer className="h-10 py-2 bg-background flex items-center text-muted-foreground text-md px-1 border-t border-border select-none no-print text-sm shadow-[0_0_4px_1px_rgba(0,0,0,0.1)] z-50 print:hidden hide-on-fullscreen">
      <FooterItem
        tooltip={errorPanel.tooltip}
        selected={selectedPanel === errorPanel.type}
        onClick={() => toggleApplication(errorPanel.type)}
      >
        {renderIcon(errorPanel, errorCount > 0 ? "text-destructive" : "")}
        <span className="ml-1 font-mono mt-[0.125rem]">{errorCount}</span>
      </FooterItem>

      <IfCapability capability="terminal">
        <FooterItem
          tooltip="Open terminal"
          selected={isTerminalOpen}
          onClick={() => toggleTerminal()}
        >
          <TerminalSquareIcon className="h-5 w-5" />
        </FooterItem>
      </IfCapability>

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
            <ZapOffIcon size={14} />
          )}
          <span>{config.runtime.auto_instantiate ? "autorun" : "lazy"}</span>
        </div>
      </FooterItem>

      <div className="border-r border-border h-6 mx-1" />

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
            <ZapOffIcon size={14} />
          )}
          <span>{config.runtime.on_cell_change}</span>
        </div>
      </FooterItem>

      <div className="border-r border-border h-6 mx-1" />

      {!isWasm() && (
        <FooterItem tooltip={null} selected={false}>
          <DropdownMenu>
            <DropdownMenuTrigger className="font-prose text-sm flex items-center gap-1">
              <span>on module change: </span>
              {config.runtime.auto_reload === "off" && (
                <PowerOffIcon size={14} />
              )}
              {config.runtime.auto_reload === "lazy" && (
                <ZapOffIcon size={14} />
              )}
              {config.runtime.auto_reload === "autorun" && (
                <ZapIcon size={14} />
              )}
              <span>{config.runtime.auto_reload}</span>
              <ChevronDownIcon size={14} />
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              {["off", "lazy", "autorun"].map((option) => (
                <DropdownMenuItem
                  key={option}
                  onClick={async () => {
                    const newConfig: UserConfig = {
                      ...config,
                      runtime: {
                        ...config.runtime,
                        auto_reload: option as "off" | "lazy" | "autorun",
                      },
                    };
                    await saveUserConfig({ config: newConfig }).then(() =>
                      setConfig(newConfig),
                    );
                  }}
                >
                  {option === "off" && (
                    <PowerOffIcon
                      size={14}
                      className="mr-2 text-muted-foreground"
                    />
                  )}
                  {option === "lazy" && (
                    <ZapOffIcon
                      size={14}
                      className="mr-2 text-muted-foreground"
                    />
                  )}
                  {option === "autorun" && (
                    <ZapIcon size={14} className="mr-2 text-muted-foreground" />
                  )}
                  {option}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </FooterItem>
      )}

      <div className="mx-auto" />

      <ShowInKioskMode>
        <Tooltip
          content={
            <div className="w-[200px]">
              Kiosk mode is enabled. This allows you to view the outputs of the
              cells without the ability to edit them.
            </div>
          }
        >
          <span className="text-muted-foreground text-sm mr-4">kiosk mode</span>
        </Tooltip>
      </ShowInKioskMode>

      <div className="flex items-center">
        <MachineStats />
        <AIStatusIcon />
        <CopilotStatusIcon />
        <RTCStatus />
        <BackendConnection />
      </div>
    </footer>
  );
};
