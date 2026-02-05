/* Copyright 2026 Marimo. All rights reserved. */
import "../css/index.css";
import "../css/app/App.css";
import "iconify-icon";

import { Provider as SlotzProvider } from "@marimo-team/react-slotz";
import type React from "react";
import { memo, type PropsWithChildren, Suspense } from "react";
import { TailwindIndicator } from "@/components/debug/indicator";
import { useAppConfig, useResolvedMarimoConfig } from "@/core/config/config";
import { getInitialAppMode } from "@/core/mode";
import { CssVariables } from "@/theme/ThemeProvider";
import { reactLazyWithPreload } from "@/utils/lazy";
import { ErrorBoundary } from "../components/editor/boundary/ErrorBoundary";
import { KernelStartupErrorModal } from "../components/editor/KernelStartupErrorModal";
import { ModalProvider } from "../components/modal/ImperativeModal";
import { Toaster } from "../components/ui/toaster";
import { TooltipProvider } from "../components/ui/tooltip";
import { LocaleProvider } from "./i18n/locale-provider";
import { slotsController } from "./slots/slots";

// Force tailwind classnames
// tailwind only creates css for classnames that exist the FE files
export const FORCE_TW_CLASSES =
  "prose prose-sm prose-base prose-lg prose-xl prose-2xl dark:prose-invert";

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
const LazyGalleryPage = reactLazyWithPreload(
  () => import("@/components/pages/gallery-page"),
);

export function preloadPage(mode: string) {
  switch (mode) {
    case "home":
      LazyHomePage.preload();
      break;
    case "gallery":
      LazyGalleryPage.preload();
      break;
    case "read":
      LazyRunPage.preload();
      break;
    default:
      LazyEditPage.preload();
  }
}

/**
 * The root component of the Marimo app.
 */
export const MarimoApp: React.FC = memo(() => {
  const [userConfig] = useResolvedMarimoConfig();
  const [appConfig] = useAppConfig();
  const editorFontSize = toRem(userConfig.display.code_editor_font_size);

  const renderBody = () => {
    const initialMode = getInitialAppMode();
    if (initialMode === "home") {
      return <LazyHomePage.Component />;
    }
    if (initialMode === "gallery") {
      return <LazyGalleryPage.Component />;
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
        <LocaleProvider>{renderBody()}</LocaleProvider>
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
          <SlotzProvider controller={slotsController}>
            <LocaleProvider>
              <ModalProvider>
                {children}
                <Toaster />
                <TailwindIndicator />
                <KernelStartupErrorModal />
              </ModalProvider>
            </LocaleProvider>
          </SlotzProvider>
        </TooltipProvider>
      </Suspense>
    </ErrorBoundary>
  );
});
Providers.displayName = "Providers";

function toRem(px: number) {
  return `${px / 16}rem`;
}
