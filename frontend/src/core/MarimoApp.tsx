/* Copyright 2024 Marimo. All rights reserved. */
import "../css/index.css";
import "../css/app/App.css";
import "iconify-icon";

import type React from "react";
import { type PropsWithChildren, Suspense, memo } from "react";
import { ErrorBoundary } from "../components/editor/boundary/ErrorBoundary";
import { TooltipProvider } from "../components/ui/tooltip";
import { Toaster } from "../components/ui/toaster";
import { ModalProvider } from "../components/modal/ImperativeModal";
import { DayPickerProvider } from "react-day-picker";
import { useAppConfig, useUserConfig } from "@/core/config/config";
import { initialMode } from "./mode";
import { CssVariables } from "@/theme/ThemeProvider";
import { TailwindIndicator } from "@/components/debug/indicator";
import { Provider as SlotzProvider } from "@marimo-team/react-slotz";
import { slotsController } from "./slots/slots";
import { reactLazyWithPreload } from "@/utils/lazy";

// Force tailwind classnames
// tailwind only creates css for classnames that exist the FE files
export const FORCE_TW_CLASSES = "prose";

// Lazy imports
const LazyHomePage = reactLazyWithPreload(
  () => import("@/components/pages/home-page"),
);
const LazyRunPage = reactLazyWithPreload(
  () => import("@/components/pages/run-page"),
);
const LazyEditPage = reactLazyWithPreload(
  () => import("@/components/pages/edit-page"),
);

function preload(mode: string) {
  if (mode === "home") {
    LazyHomePage.preload();
  } else if (mode === "read") {
    LazyRunPage.preload();
  } else {
    LazyEditPage.preload();
  }
}
preload(initialMode);

/**
 * The root component of the Marimo app.
 */
export const MarimoApp: React.FC = memo(() => {
  const [userConfig] = useUserConfig();
  const [appConfig] = useAppConfig();
  const editorFontSize = toRem(userConfig.display.code_editor_font_size);

  const renderBody = () => {
    if (initialMode === "home") {
      return <LazyHomePage.Component />;
    }
    if (initialMode === "read") {
      return <LazyRunPage.Component appConfig={appConfig} />;
    }
    return (
      <LazyEditPage.Component userConfig={userConfig} appConfig={appConfig} />
    );
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
            <SlotzProvider controller={slotsController}>
              <ModalProvider>
                {children}
                <Toaster />
                <TailwindIndicator />
              </ModalProvider>
            </SlotzProvider>
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
