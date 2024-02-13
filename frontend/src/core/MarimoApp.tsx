/* Copyright 2024 Marimo. All rights reserved. */
import "../css/index.css";
import "iconify-icon";

import { useEffect } from "react";
import { ErrorBoundary } from "../components/editor/boundary/ErrorBoundary";
import { initializePlugins } from "../plugins/plugins";
import { App } from "./App";
import { TooltipProvider } from "../components/ui/tooltip";
import { Toaster } from "../components/ui/toaster";
import { ModalProvider } from "../components/modal/ImperativeModal";
import { DayPickerProvider } from "react-day-picker";
import { CommandPalette } from "../components/editor/CommandPalette";
import { useAppConfig, useUserConfig } from "@/core/config/config";
import { initialMode } from "./mode";
import { AppChrome } from "../components/editor/chrome/wrapper/app-chrome";
import { StaticBanner } from "../components/static-html/static-banner";
import { CssVariables } from "@/theme/ThemeProvider";
import { useAsyncData } from "@/hooks/useAsyncData";
import { isPyodide } from "./pyodide/utils";
import { PyodideBridge } from "./pyodide/bridge";
import { LargeSpinner } from "@/components/icons/large-spinner";

/**
 * The root component of the Marimo app.
 */
export const MarimoApp: React.FC = () => {
  const [userConfig] = useUserConfig();
  const [appConfig] = useAppConfig();

  const { loading } = useAsyncData(async () => {
    if (isPyodide()) {
      await PyodideBridge.INSTANCE.initialize();
    }
    return true;
  }, []);

  useEffect(() => {
    initializePlugins();
  }, []);

  if (loading) {
    return <LargeSpinner />;
  }

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
        <CommandPalette />
      </AppChrome>
    );

  return (
    <ErrorBoundary>
      <TooltipProvider>
        <DayPickerProvider initialProps={{}}>
          <ModalProvider>
            <CssVariables
              variables={{
                "--marimo-code-editor-font-size": toRem(
                  userConfig.display.code_editor_font_size,
                ),
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

function toRem(px: number) {
  return `${px / 16}rem`;
}
