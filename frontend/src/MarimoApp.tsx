/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect } from "react";
import "./css/index.css";
import { ErrorBoundary } from "./editor/boundary/ErrorBoundary";
import { initializePlugins } from "./plugins/plugins";
import { App } from "./App";
import { TooltipProvider } from "./components/ui/tooltip";
import { Toaster } from "./components/ui/toaster";
import { ModalProvider } from "./components/modal/ImperativeModal";
import { DayPickerProvider } from "react-day-picker";
import { CommandPallette } from "./editor/CommandPallette";
import { useAppConfig, useUserConfig } from "@/core/state/config";
import { initialMode } from "./core/mode";
import { AppChrome } from "./editor/chrome/wrapper/app-chrome";
import { StaticBanner } from "./components/static-html/static-banner";

/**
 * The root component of the Marimo app.
 */
export const MarimoApp: React.FC = () => {
  const [userConfig] = useUserConfig();
  const [appConfig] = useAppConfig();

  useEffect(() => {
    initializePlugins();
  }, []);

  const body =
    initialMode === "read" ? (
      <>
        <StaticBanner />
        <App userConfig={userConfig} appConfig={appConfig} />
        <Toaster />
      </>
    ) : (
      <AppChrome>
        <App userConfig={userConfig} appConfig={appConfig} />
        <Toaster />
        <CommandPallette />
      </AppChrome>
    );

  return (
    <ErrorBoundary>
      <TooltipProvider>
        <DayPickerProvider initialProps={{}}>
          <ModalProvider>{body}</ModalProvider>
        </DayPickerProvider>
      </TooltipProvider>
    </ErrorBoundary>
  );
};
