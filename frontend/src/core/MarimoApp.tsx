/* Copyright 2023 Marimo. All rights reserved. */
import "../css/index.css";

import { useEffect } from "react";
import { ErrorBoundary } from "../components/editor/boundary/ErrorBoundary";
import { initializePlugins } from "../plugins/plugins";
import { App } from "./App";
import { TooltipProvider } from "../components/ui/tooltip";
import { Toaster } from "../components/ui/toaster";
import { ModalProvider } from "../components/modal/ImperativeModal";
import { DayPickerProvider } from "react-day-picker";
import { CommandPallette } from "../components/editor/CommandPallette";
import { useAppConfig, useUserConfig } from "@/core/config/config";
import { initialMode } from "./mode";
import { AppChrome } from "../components/editor/chrome/wrapper/app-chrome";
import { StaticBanner } from "../components/static-html/static-banner";
import { CssVariables } from "@/theme/ThemeProvider";

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
          <ModalProvider>
            <CssVariables
              variables={{
                "--marimo-api-code-editor-font-size": `${userConfig.display.code_editor_font_size}px`,
              }}
            >
              {body}
            </CssVariables>
          </ModalProvider>
        </DayPickerProvider>
      </TooltipProvider>
    </ErrorBoundary>
  );
};
