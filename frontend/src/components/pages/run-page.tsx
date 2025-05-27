/* Copyright 2024 Marimo. All rights reserved. */
import type { AppConfig } from "@/core/config/config-schema";
import { RunApp } from "@/core/run-app";
import { StaticBanner } from "../static-html/static-banner";
import { isStaticNotebook } from "@/core/static/static-state";
import { isWasm } from "@/core/wasm/utils";
import { Constants } from "@/core/constants";
import { ContextAwarePanel } from "../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { PanelGroup, Panel } from "react-resizable-panels";
import { createStorage } from "../editor/chrome/wrapper/storage";
import { PanelsWrapper } from "../editor/chrome/wrapper/panels";

interface Props {
  appConfig: AppConfig;
}

const showWatermark = isWasm() || isStaticNotebook();

const RunPage = (props: Props) => {
  return (
    <PanelsWrapper>
      <PanelGroup
        direction="horizontal"
        autoSaveId="marimo:chrome:v1:run1"
        storage={createStorage("left")}
      >
        <StaticBanner />
        <Panel>
          <RunApp appConfig={props.appConfig} />
          {showWatermark && <Watermark />}
        </Panel>
        <ContextAwarePanel />
      </PanelGroup>
    </PanelsWrapper>
  );
};

const Watermark = () => {
  return (
    <div className="fixed bottom-0 right-0 z-50">
      <a
        href={Constants.githubPage}
        target="_blank"
        className="text-sm text-[var(--grass-11)] font-bold tracking-wide transition-colors bg-[var(--grass-4)] hover:bg-[var(--grass-5)] border-t border-l border-[var(--grass-8)] px-3 py-1 rounded-tl-md flex items-center gap-2"
      >
        <span className="pb-[2px]">made with marimo</span>
        <img src="./favicon.ico" alt="marimo" className="h-4 w-auto" />
      </a>
    </div>
  );
};

export default RunPage;
