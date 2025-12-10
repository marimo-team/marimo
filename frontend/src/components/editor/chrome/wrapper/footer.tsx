/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { TerminalSquareIcon, XCircleIcon } from "lucide-react";
import type React from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { cellErrorCount } from "@/core/cells/cells";
import { IfCapability } from "@/core/config/if-capability";
import { useHotkey } from "@/hooks/useHotkey";
import { cn } from "@/utils/cn";
import { ShowInKioskMode } from "../../kiosk-mode";
import { useChromeActions, useChromeState } from "../state";
import { FooterItem } from "./footer-item";
import { AIStatusIcon } from "./footer-items/ai-status";
import { BackendConnection } from "./footer-items/backend-status";
import { CopilotStatusIcon } from "./footer-items/copilot-status";
import { MachineStats } from "./footer-items/machine-stats";
import { MinimapStatusIcon } from "./footer-items/minimap-status";
import { RTCStatus } from "./footer-items/rtc-status";
import { RuntimeSettings } from "./footer-items/runtime-settings";

export const Footer: React.FC = () => {
  const { isPanelOpen, selectedPanelTab } = useChromeState();
  const { togglePanel, openPanelTab } = useChromeActions();
  const errorCount = useAtomValue(cellErrorCount);

  useHotkey("global.toggleTerminal", () => {
    togglePanel();
  });

  useHotkey("global.togglePanel", () => {
    togglePanel();
  });

  return (
    <footer className="h-10 py-2 bg-background flex items-center text-muted-foreground text-md px-1 border-t border-border select-none no-print text-sm shadow-[0_0_4px_1px_rgba(0,0,0,0.1)] z-50 print:hidden hide-on-fullscreen overflow-x-auto overflow-y-hidden scrollbar-thin">
      <FooterItem
        tooltip="View errors"
        selected={isPanelOpen && selectedPanelTab === "errors"}
        onClick={() => openPanelTab("errors")}
        data-testid="footer-errors"
      >
        <XCircleIcon className={cn("h-5 w-5", errorCount > 0 && "text-destructive")} />
        <span className="ml-1 font-mono mt-0.5">{errorCount}</span>
      </FooterItem>

      <IfCapability capability="terminal">
        <FooterItem
          tooltip="Toggle developer panel"
          selected={isPanelOpen}
          onClick={() => togglePanel()}
          data-testid="footer-panel"
        >
          <TerminalSquareIcon className="h-5 w-5" />
        </FooterItem>
      </IfCapability>

      <RuntimeSettings />

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

      <div className="flex items-center shrink-0 min-w-0">
        <MachineStats />
        <MinimapStatusIcon />
        <AIStatusIcon />
        <CopilotStatusIcon />
        <RTCStatus />
        <BackendConnection />
      </div>
    </footer>
  );
};
