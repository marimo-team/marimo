/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { AlertTriangleIcon, XCircleIcon } from "lucide-react";
import type React from "react";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
import { cellErrorCount } from "@/core/cells/cells";
import { IfCapability } from "@/core/config/if-capability";
import { useHotkey } from "@/hooks/useHotkey";
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
  const { isDeveloperPanelOpen } = useChromeState();
  const { toggleDeveloperPanel } = useChromeActions();

  const errorCount = useAtomValue(cellErrorCount);

  // TODO: Add warning count from diagnostics/linting
  // This can signal warnings/errors with settings up AI / Copilot etc
  const warningCount = 0;

  useHotkey("global.toggleTerminal", () => {
    toggleDeveloperPanel();
  });

  useHotkey("global.togglePanel", () => {
    toggleDeveloperPanel();
  });

  return (
    <footer className="h-10 py-2 bg-background flex items-center text-muted-foreground text-md pl-2 pr-1 border-t border-border select-none no-print text-sm shadow-[0_0_4px_1px_rgba(0,0,0,0.1)] z-50 print:hidden hide-on-fullscreen overflow-x-auto overflow-y-hidden scrollbar-thin">
      <IfCapability capability="terminal">
        <div className="flex items-center">
          <div className="flex">
            <FooterItem
              tooltip={
                <span className="flex items-center gap-2">
                  Toggle developer panel{" "}
                  {renderShortcut("global.togglePanel", false)}
                </span>
              }
              selected={isDeveloperPanelOpen}
              onClick={() => toggleDeveloperPanel()}
              data-testid="footer-panel"
            >
              <div className="flex items-center gap-1">
                <XCircleIcon
                  className={`w-4 h-4 ${errorCount > 0 ? "text-destructive" : ""}`}
                />
                <span>{errorCount}</span>
                <AlertTriangleIcon
                  className={`w-4 h-4 ml-1 ${warningCount > 0 ? "text-yellow-500" : ""}`}
                />
                <span>{warningCount}</span>
              </div>
            </FooterItem>
          </div>
        </div>
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
