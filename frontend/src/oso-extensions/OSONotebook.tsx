/* Copyright 2024 Marimo. All rights reserved. */
import "../css/index.css";
import "../css/app/App.css";
import "iconify-icon";

import { Provider as SlotzProvider } from "@marimo-team/react-slotz";
import type React from "react";
import { memo, type PropsWithChildren, Suspense, useEffect } from "react";
import { TailwindIndicator } from "@/components/debug/indicator";
import { useAppConfig, useResolvedMarimoConfig } from "@/core/config/config";
import { CssVariables } from "@/theme/ThemeProvider";
import { reactLazyWithPreload } from "@/utils/lazy";
import { ErrorBoundary } from "../components/editor/boundary/ErrorBoundary";
import { ModalProvider } from "../components/modal/ImperativeModal";
import { Toaster } from "../components/ui/toaster";
import { TooltipProvider } from "../components/ui/tooltip";
import { slotsController } from "../core/slots/slots";
import { useFragmentStore } from "./fragment-store";
import { viewStateAtom } from "@/core/mode";
import { useSetAtom } from "jotai";

// Force tailwind classnames
// tailwind only creates css for classnames that exist the FE files
export const FORCE_TW_CLASSES =
  "prose prose-sm prose-base prose-lg prose-xl prose-2xl dark:prose-invert";

export const LazyOSONotebookEditPage = reactLazyWithPreload(() => import("@/oso-extensions/oso-notebook-edit-page"));
export const LazyOSONotebookRunPage = reactLazyWithPreload(() => import("@/oso-extensions/oso-notebook-run-page"));

export function preloadPage(mode: string) {
  if (mode === "edit") {
    LazyOSONotebookEditPage.preload();
  } else {
    LazyOSONotebookRunPage.preload();
  }
}

/**
 * The root component of the OSONotebook app.
 */
export const OSONotebook: React.FC = memo(() => {
  const [userConfig] = useResolvedMarimoConfig();
  const [appConfig] = useAppConfig();
  const editorFontSize = toRem(userConfig.display.code_editor_font_size);
  const fragmentStore = useFragmentStore();
  const setViewState = useSetAtom(viewStateAtom);

  const mode = fragmentStore.getString("mode", "edit") === "edit" ? "edit" : "read";
  const appMode = fragmentStore.getBoolean("enablePresentMode");

  useEffect(() => {
    if (appMode) {
      setViewState({
        mode: "present",
        cellAnchor: null,
      });
    }
  }, [])

  const renderBody = (mode: string) => {
    if (mode === "edit") {
      return (
        <LazyOSONotebookEditPage.Component userConfig={userConfig} appConfig={appConfig} />
      );
    }
    console.log("LOADING RUN PAGE");
    return (
      <LazyOSONotebookRunPage.Component appConfig={appConfig} />
    );
  };

  return (
    <Providers>
      <CssVariables
        variables={{ "--marimo-code-editor-font-size": editorFontSize }}
      >
        {renderBody(mode)}
      </CssVariables>
    </Providers>
  );
});
OSONotebook.displayName = "OSONotebook";

/**
 * The root with all the providers.
 */
const Providers = memo(({ children }: PropsWithChildren) => {
  return (
    <ErrorBoundary>
      <Suspense>
        <TooltipProvider>
          <SlotzProvider controller={slotsController}>
            <ModalProvider>
              {children}
              <Toaster />
              <TailwindIndicator />
            </ModalProvider>
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
