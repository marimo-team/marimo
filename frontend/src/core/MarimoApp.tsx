/* Copyright 2024 Marimo. All rights reserved. */
import "../css/index.css";
import "../css/app/App.css";
import "iconify-icon";

import React, { PropsWithChildren, Suspense, memo } from "react";
import { ErrorBoundary } from "../components/editor/boundary/ErrorBoundary";
import { TooltipProvider } from "../components/ui/tooltip";
import { Toaster } from "../components/ui/toaster";
import { ModalProvider } from "../components/modal/ImperativeModal";
import { DayPickerProvider } from "react-day-picker";
import { useAppConfig, useUserConfig } from "@/core/config/config";
import { initialMode } from "./mode";
import { CssVariables } from "@/theme/ThemeProvider";
import { useAsyncData } from "@/hooks/useAsyncData";
import { isPyodide } from "./pyodide/utils";
import { PyodideBridge } from "./pyodide/bridge";
import { LargeSpinner } from "@/components/icons/large-spinner";
import { TailwindIndicator } from "@/components/debug/indicator";
import { Provider as SlotzProvider } from "@marimo-team/react-slotz";
import { slotsController } from "./slots/slots";

// Lazy imports
const LazyHomePage = React.lazy(() => import("@/components/pages/home-page"));
const LazyRunPage = React.lazy(() => import("@/components/pages/run-page"));
const LazyEditPage = React.lazy(() => import("@/components/pages/edit-page"));

/**
 * The root component of the Marimo app.
 */
export const MarimoApp: React.FC = memo(() => {
  const [userConfig] = useUserConfig();
  const [appConfig] = useAppConfig();
  const editorFontSize = toRem(userConfig.display.code_editor_font_size);

  const renderBody = () => {
    if (initialMode === "home") {
      return <LazyHomePage />;
    } else if (initialMode === "read") {
      return <LazyRunPage appConfig={appConfig} />;
    } else {
      return <LazyEditPage userConfig={userConfig} appConfig={appConfig} />;
    }
  };

  return (
    <Providers>
      <CssVariables
        variables={{ "--marimo-code-editor-font-size": editorFontSize }}
      >
        {renderBody()}
      </CssVariables>
    </Providers>
  );
});
MarimoApp.displayName = "MarimoApp";

/**
 * The root with all the providers.
 */
const Providers = memo(({ children }: PropsWithChildren) => {
  return (
    <ErrorBoundary>
      <Suspense>
        <TooltipProvider>
          <DayPickerProvider initialProps={{}}>
            <PyodideLoader>
              <SlotzProvider controller={slotsController}>
                <ModalProvider>
                  {children}
                  <Toaster />
                  <TailwindIndicator />
                </ModalProvider>
              </SlotzProvider>
            </PyodideLoader>
          </DayPickerProvider>
        </TooltipProvider>
      </Suspense>
    </ErrorBoundary>
  );
});
Providers.displayName = "Providers";

function toRem(px: number) {
  return `${px / 16}rem`;
}

/**
 * HOC to load Pyodide before rendering children, if necessary.
 */
const PyodideLoader: React.FC<PropsWithChildren> = ({ children }) => {
  if (!isPyodide()) {
    return children;
  }

  // isPyodide() is constant, so this is safe
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const { loading, error } = useAsyncData(async () => {
    await PyodideBridge.INSTANCE.initialized.promise;
    return true;
  }, []);

  if (loading) {
    return <LargeSpinner />;
  }

  // Propagate back up to our error boundary
  if (error) {
    throw error;
  }

  return children;
};
