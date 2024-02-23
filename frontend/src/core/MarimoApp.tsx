/* Copyright 2024 Marimo. All rights reserved. */
import "../css/index.css";
import "iconify-icon";

import { PropsWithChildren, memo, useEffect } from "react";
import { ErrorBoundary } from "../components/editor/boundary/ErrorBoundary";
import { initializePlugins } from "../plugins/plugins";
import { App } from "./App";
import { TooltipProvider } from "../components/ui/tooltip";
import { Toaster } from "../components/ui/toaster";
import { ModalProvider } from "../components/modal/ImperativeModal";
import { DayPickerProvider } from "react-day-picker";
import { CommandPalette } from "../components/editor/controls/command-palette";
import { useAppConfig, useUserConfig } from "@/core/config/config";
import { initialMode } from "./mode";
import { AppChrome } from "../components/editor/chrome/wrapper/app-chrome";
import { StaticBanner } from "../components/static-html/static-banner";
import { CssVariables } from "@/theme/ThemeProvider";
import { useAsyncData } from "@/hooks/useAsyncData";
import { isPyodide } from "./pyodide/utils";
import { PyodideBridge } from "./pyodide/bridge";
import { LargeSpinner } from "@/components/icons/large-spinner";
import { TailwindIndicator } from "@/components/indicator";

/**
 * The root component of the Marimo app.
 */
export const MarimoApp: React.FC = memo(() => {
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
        <CommandPalette />
      </AppChrome>
    );

  return (
    <ErrorBoundary>
      <TooltipProvider>
        <DayPickerProvider initialProps={{}}>
          <PyodideLoader>
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
              <TailwindIndicator />
            </ModalProvider>
          </PyodideLoader>
        </DayPickerProvider>
      </TooltipProvider>
    </ErrorBoundary>
  );
});
MarimoApp.displayName = "MarimoApp";

function toRem(px: number) {
  return `${px / 16}rem`;
}

export const PyodideLoader: React.FC<PropsWithChildren> = ({ children }) => {
  if (!isPyodide()) {
    return children;
  }

  // isPyodide() is constant, so this is safe
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const { loading } = useAsyncData(async () => {
    await PyodideBridge.INSTANCE.initialized.promise;
    return true;
  }, []);

  if (loading) {
    return <LargeSpinner />;
  }

  return children;
};
