/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { AlertCircleIcon, CheckCircle2Icon, PowerOffIcon } from "lucide-react";
import type React from "react";
import { LoadingEllipsis } from "@/components/icons/loading-ellipsis";
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { DelayMount } from "@/components/utils/delay-mount";
import { type AdapterState, runtimeAdapterAtom } from "@/core/runtime/adapter";
import { Banner } from "@/plugins/impl/common/error-banner";

type Surface = "footer" | "header" | "alert";
type ShowWhen = "active" | "always";

interface Props {
  /**
   * - `footer`: small pill suitable for the chrome footer.
   * - `header`: icon-only overlay in the corner of the editor.
   * - `alert`: full-width slide-down banner for transient connection issues.
   */
  surface: Surface;
  /**
   * `active` (default) hides the badge when the runtime is healthy.
   * `always` shows a check mark in steady state instead.
   */
  showWhen?: ShowWhen;
  /** Alert-surface only: debounce before the banner appears. */
  delayMs?: number;
}
export const RuntimeStatusBadge: React.FC<Props> = ({
  surface,
  showWhen = "active",
  delayMs,
}) => {
  const adapter = useAtomValue(runtimeAdapterAtom);
  const state = useAtomValue(adapter.state);

  if (showWhen === "active" && state.kind === "ready") {
    return null;
  }

  const tooltip = tooltipFor(state, adapter.label);

  switch (surface) {
    case "footer":
      return (
        <FooterPill state={state} tooltip={tooltip} label={adapter.label} />
      );
    case "header":
      return <HeaderOverlay state={state} tooltip={tooltip} />;
    case "alert":
      return (
        <AlertBanner
          state={state}
          tooltip={tooltip}
          delayMs={delayMs ?? 1000}
        />
      );
  }
};

function tooltipFor(state: AdapterState, label: string): string {
  switch (state.kind) {
    case "failed":
      return state.error.message;
    case "connecting":
      return state.progress?.label ?? `${label} starting…`;
    case "ready":
      return `${label} ready`;
  }
}

interface RenderProps {
  state: AdapterState;
  tooltip: string;
  label?: string;
  delayMs?: number;
}

const FooterPill: React.FC<RenderProps> = ({ state, tooltip, label }) => {
  const icon =
    state.kind === "failed" ? (
      <AlertCircleIcon className="w-4 h-4 text-destructive" />
    ) : state.kind === "ready" ? (
      <CheckCircle2Icon className="w-4 h-4 text-(--green-9)" />
    ) : (
      <Spinner size="small" />
    );

  return (
    <Tooltip
      content={<div className="text-sm whitespace-pre-line">{tooltip}</div>}
      data-testid="footer-runtime-status"
    >
      <div
        className="p-1 hover:bg-accent rounded flex items-center gap-1.5 text-xs text-muted-foreground"
        data-testid="runtime-status-footer"
      >
        {icon}
        {label && <span>{label}</span>}
      </div>
    </Tooltip>
  );
};

const HeaderOverlay: React.FC<RenderProps> = ({ state, tooltip }) => {
  if (state.kind === "ready") {
    return null;
  }
  const icon =
    state.kind === "failed" ? (
      <PowerOffIcon className="w-[25px] h-[25px] text-(--red-11)" />
    ) : (
      <LoadingEllipsis size={5} className="text-yellow-500" />
    );
  return (
    <Tooltip content={tooltip}>
      <div
        className="print:hidden pointer-events-auto"
        data-testid="runtime-status-header"
      >
        {icon}
      </div>
    </Tooltip>
  );
};

const AlertBanner: React.FC<RenderProps> = ({ state, tooltip, delayMs }) => {
  if (state.kind === "ready") {
    return null;
  }
  const kind: "info" | "danger" = state.kind === "failed" ? "danger" : "info";

  return (
    <DelayMount milliseconds={delayMs ?? 0}>
      <div
        className="m-0 flex items-center min-h-[28px] fixed top-5 left-1/2 transform -translate-x-1/2 z-200"
        data-testid="runtime-status-alert"
      >
        <Banner
          kind={kind}
          className="flex flex-col rounded py-2 px-4 animate-in slide-in-from-top w-fit"
        >
          <div className="flex items-center gap-2 text-muted-foreground text-base">
            {kind === "info" ? <Spinner className="h-4 w-4" /> : null}
            <p>{tooltip}</p>
          </div>
        </Banner>
      </div>
    </DelayMount>
  );
};
