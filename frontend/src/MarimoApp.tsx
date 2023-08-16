/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect } from "react";
import "./css/index.css";
import { ErrorBoundary } from "./editor/boundary/ErrorBoundary";
import { initializePlugins } from "./plugins/plugins";
import { App } from "./App";
import { AppMode } from "./core/mode";
import { TooltipProvider } from "./components/ui/tooltip";
import { Toaster } from "./components/ui/toaster";
import { ModalProvider } from "./components/modal/ImperativeModal";
import { DayPickerProvider } from "react-day-picker";
import { CommandPallette } from "./editor/CommandPallette";
import { useAppConfig, useUserConfig } from "@/core/state/config";

interface MarimoAppProps {
  /**
   * The mode of the Marimo app.
   */
  initialMode: AppMode;
}

/**
 * The root component of the Marimo app.
 */
export const MarimoApp: React.FC<MarimoAppProps> = ({ initialMode }) => {
  const [userConfig] = useUserConfig();
  const [appConfig] = useAppConfig();

  useEffect(() => {
    initializePlugins();
  }, []);

  return (
    <ErrorBoundary>
      <TooltipProvider>
        <DayPickerProvider initialProps={{}}>
          <ModalProvider>
            <App
              initialMode={initialMode}
              userConfig={userConfig}
              appConfig={appConfig}
            />
            <Toaster />
            {initialMode !== "read" && <CommandPallette />}
          </ModalProvider>
        </DayPickerProvider>
      </TooltipProvider>
    </ErrorBoundary>
  );
};
