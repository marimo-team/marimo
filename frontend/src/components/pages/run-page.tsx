/* Copyright 2026 Marimo. All rights reserved. */

import { Panel, PanelGroup } from "react-resizable-panels";
import { useAtomValue } from "jotai";
import { MarimoIcon } from "@/components/icons/marimo-icons";
import type { AppConfig } from "@/core/config/config-schema";
import { Constants } from "@/core/constants";
import { resolveLayoutType, useLayoutState } from "@/core/layout/state";
import { RunApp } from "@/core/run-app";
import { runtimeAdapterAtom } from "@/core/runtime/adapter";
import { ContextAwarePanel } from "../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { PanelsWrapper } from "../editor/chrome/wrapper/panels";
import { StaticBanner } from "../static-html/static-banner";

interface Props {
  appConfig: AppConfig;
}

const RunPage = (props: Props) => {
  const runtimeKind = useAtomValue(runtimeAdapterAtom).kind;
  const isExportedNotebook = runtimeKind === "static" || runtimeKind === "wasm";
  const { selectedLayout } = useLayoutState();
  const finalLayout = resolveLayoutType({
    selectedLayout,
    isReading: true,
    searchParams: new URLSearchParams(window.location.search),
  });
  const isExportedSlides = isExportedNotebook && finalLayout === "slides";

  return (
    <PanelsWrapper>
      <PanelGroup direction="horizontal" autoSaveId="marimo:chrome:v1:run1">
        <Panel>
          {!isExportedSlides && <StaticBanner />}
          <RunApp appConfig={props.appConfig} hideHeader={isExportedSlides} />
          {isExportedNotebook && !isExportedSlides && <Watermark />}
        </Panel>
        <ContextAwarePanel />
      </PanelGroup>
    </PanelsWrapper>
  );
};

const Watermark = () => {
  return (
    <div
      className="fixed bottom-0 right-0 z-50 print:hidden"
      data-testid="watermark"
    >
      <a
        href={Constants.githubPage}
        target="_blank"
        className="text-sm text-(--grass-11) font-bold tracking-wide transition-colors bg-(--grass-4) hover:bg-(--grass-5) border-t border-l border-(--grass-8) px-3 py-1 rounded-tl-md flex items-center gap-2"
      >
        <span>made with marimo</span>
        <MarimoIcon className="h-4 w-auto" />
      </a>
    </div>
  );
};

export default RunPage;
