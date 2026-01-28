/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { AlertTriangleIcon, XCircleIcon } from "lucide-react";
import type React from "react";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
import { cellErrorCount } from "@/core/cells/cells";
import { isConnectingAtom } from "@/core/network/connection";
import { useHotkey } from "@/hooks/useHotkey";
import { ShowInKioskMode } from "../../kiosk-mode";
import { panelLayoutAtom, useChromeActions, useChromeState } from "../state";
import { FooterItem } from "./footer-item";
import { AIStatusIcon } from "./footer-items/ai-status";
import {
  BackendConnectionStatus,
  connectionStatusAtom,
} from "./footer-items/backend-status";
import { CopilotStatusIcon } from "./footer-items/copilot-status";
import { MachineStats } from "./footer-items/machine-stats";
import { RTCStatus } from "./footer-items/rtc-status";
import { RuntimeSettings } from "./footer-items/runtime-settings";
import { useSetDependencyPanelTab } from "./useDependencyPanelTab";

export const Footer: React.FC = () => {
  const { isDeveloperPanelOpen } = useChromeState();
  const { toggleDeveloperPanel, toggleApplication } = useChromeActions();
  const setDependencyPanelTab = useSetDependencyPanelTab();

  const errorCount = useAtomValue(cellErrorCount);
  const connectionStatus = useAtomValue(connectionStatusAtom);
  const panelLayout = useAtomValue(panelLayoutAtom);

  // Show issue count: cell errors + connection issues
  // Don't include error count if errors panel is in sidebar (it shows there instead)
  const errorsInSidebar = panelLayout.sidebar.includes("errors");
  const hasConnectionIssue =
    connectionStatus === "unhealthy" || connectionStatus === "disconnected";
  const issueCount =
    (errorsInSidebar ? 0 : errorCount) + (hasConnectionIssue ? 1 : 0);

  // TODO: Add warning count from diagnostics/linting
  // This can signal warnings/errors with settings up AI / Copilot etc
  const warningCount = 0;

  useHotkey("global.toggleTerminal", () => {
    toggleApplication("terminal");
  });

  useHotkey("global.togglePanel", () => {
    toggleDeveloperPanel();
  });

  useHotkey("global.toggleMinimap", () => {
    toggleApplication("dependencies");
    setDependencyPanelTab("minimap");
  });

  return (
    <footer className="h-10 py-1 gap-1 bg-background flex items-center text-muted-foreground text-md pl-2 pr-1 border-t border-border select-none print:hidden text-sm z-50 hide-on-fullscreen overflow-x-auto overflow-y-hidden scrollbar-thin">
      <FooterItem
        className="h-full"
        tooltip={
          <span className="flex items-center gap-2">
            Toggle developer panel {renderShortcut("global.togglePanel", false)}
          </span>
        }
        selected={isDeveloperPanelOpen}
        onClick={() => toggleDeveloperPanel()}
        data-testid="footer-panel"
      >
        <div className="flex items-center gap-1 h-full">
          <XCircleIcon
            className={`w-4 h-4 ${issueCount > 0 ? "text-destructive" : ""}`}
          />
          <span>{issueCount}</span>
          <AlertTriangleIcon
            className={`w-4 h-4 ml-1 ${warningCount > 0 ? "text-yellow-500" : ""}`}
          />
          <span>{warningCount}</span>
        </div>
      </FooterItem>

      <RuntimeSettings />

      <div className="mx-auto" />

      <ConnectingKernelIndicatorItem />

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
        <AIStatusIcon />
        <CopilotStatusIcon />
        <RTCStatus />
      </div>
    </footer>
  );
};

/**
 * Only show the backend connection status if we are connecting to a kernel
 */
const ConnectingKernelIndicatorItem: React.FC = () => {
  const isConnecting = useAtomValue(isConnectingAtom);
  if (!isConnecting) {
    return null;
  }
  return <BackendConnectionStatus />;
};
