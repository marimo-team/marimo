/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import {
  ProgressStages,
  ProgressStatusIcon,
  type ProgressStage,
  type ProgressState,
} from "@/components/ui/progress-stages";
import { preparationAtom } from "@/core/packages/sandbox-state";
import { startupProgressAtom } from "@/core/network/connection";
import type { DisplayConnectionNotice } from "@/core/network/useConnectionNotice";
import { StartupOutput } from "./startup-output";

const STEPS = [
  {
    phase: "preparing-environment",
    titles: {
      succeeded: "Environment prepared",
      failed: "Environment setup failed",
      running: "Preparing environment",
      waiting: "Prepare environment",
    },
    descriptions: {
      succeeded: "Python and dependencies are available.",
      failed: "Setup could not finish.",
      running: "Set up Python and dependencies.",
      waiting: "Set up Python and dependencies.",
    },
  },
  {
    phase: "starting-kernel",
    titles: {
      succeeded: "Kernel started",
      failed: "Kernel failed to start",
      running: "Starting kernel",
      waiting: "Start kernel",
    },
    descriptions: {
      succeeded: "The notebook is ready to run.",
      failed: "The kernel could not connect.",
      running: "Connecting to this notebook.",
      waiting: "After the environment is ready.",
    },
  },
] as const;

interface StartupProgressProps {
  notice: DisplayConnectionNotice;
  surface: "notebook" | "sidebar";
}

function StartupSummary({ notice }: { notice: DisplayConnectionNotice }) {
  return (
    <header>
      <output className="sr-only">{notice.title}</output>
      <h2 className="text-foreground font-heading text-2xl leading-8 tracking-tight font-normal">
        {notice.ready
          ? "Your notebook is ready"
          : "Getting your notebook ready"}
      </h2>
      <p className="text-muted-foreground mt-3 text-sm leading-6">
        {notice.ready
          ? notice.sandbox
            ? "Your environment and kernel are ready."
            : "Your kernel is ready."
          : notice.pending
            ? notice.sandbox
              ? "Preparing Python and dependencies for this notebook."
              : "Connecting to this notebook’s Python kernel."
            : "Review the setup details below to continue."}
      </p>
    </header>
  );
}

export function ConnectionStatusIcon({
  notice,
}: {
  notice: DisplayConnectionNotice;
}) {
  return (
    <ProgressStatusIcon
      state={notice.ready ? "succeeded" : notice.pending ? "running" : "failed"}
    />
  );
}

export function StartupProgress({ notice, surface }: StartupProgressProps) {
  const preparation = useAtomValue(preparationAtom);
  const progress = useAtomValue(startupProgressAtom);
  const activePhase =
    notice.phase ?? (notice.sandbox ? undefined : "starting-kernel");
  const stages: ProgressStage[] = STEPS.filter(
    (step) => notice.sandbox || step.phase === "starting-kernel",
  ).map(({ phase, titles, descriptions }) => {
    const preparing = phase === "preparing-environment";
    const state: ProgressState =
      notice.ready || (preparing && activePhase === "starting-kernel")
        ? "succeeded"
        : activePhase === phase
          ? notice.pending
            ? "running"
            : "failed"
          : "waiting";
    const logs = preparing
      ? (preparation?.logs.environment ?? "")
      : progress?.phase === phase
        ? progress.logs
        : "";
    return {
      id: phase,
      state,
      title: titles[state],
      description: descriptions[state],
      details: surface === "sidebar" && (
        <StartupOutput
          key={preparation?.operation_id}
          logs={logs}
          state={state === "waiting" ? "succeeded" : state}
          label={
            preparing
              ? "environment preparation output"
              : "kernel startup output"
          }
        />
      ),
    };
  });
  return (
    <>
      {surface === "notebook" && <StartupSummary notice={notice} />}
      <ProgressStages
        stages={stages}
        label="Notebook startup stages"
        className={surface === "notebook" ? "mt-8" : undefined}
      />
    </>
  );
}
