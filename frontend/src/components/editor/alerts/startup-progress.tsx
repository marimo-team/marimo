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

export function hasStartupStages(notice: DisplayConnectionNotice): boolean {
  return (
    notice.kind === "startup" &&
    (!notice.sandbox ||
      notice.ready ||
      notice.phase === "preparing-environment" ||
      notice.phase === "starting-kernel")
  );
}

function StartupSummary({ notice }: { notice: DisplayConnectionNotice }) {
  const getSummaryDescription = () => {
    if (notice.ready) {
      if (notice.sandbox) {
        return "Your environment and kernel are ready.";
      }
      return "Your kernel is ready.";
    }
    if (notice.pending) {
      if (notice.sandbox) {
        return "Preparing Python and dependencies for this notebook.";
      }
      return "Connecting to this notebook’s Python kernel.";
    }
    return "Review the setup details below to continue.";
  };
  return (
    <header>
      <output className="sr-only">{notice.title}</output>
      <h2 className="text-foreground font-heading text-2xl leading-8 tracking-tight font-normal">
        {notice.ready
          ? "Your notebook is ready"
          : "Getting your notebook ready"}
      </h2>
      <p className="text-muted-foreground mt-3 text-sm leading-6">
        {getSummaryDescription()}
      </p>
    </header>
  );
}

export function ConnectionStatusIcon({
  notice,
}: {
  notice: DisplayConnectionNotice;
}) {
  const getState = () => {
    if (notice.ready) {
      return "succeeded";
    }
    if (notice.pending) {
      return "running";
    }
    return "failed";
  };
  return <ProgressStatusIcon state={getState()} />;
}

export function StartupProgress({ notice, surface }: StartupProgressProps) {
  const preparation = useAtomValue(preparationAtom);
  const progress = useAtomValue(startupProgressAtom);
  const activePhase = notice.sandbox ? notice.phase : "starting-kernel";
  const stages: ProgressStage[] = STEPS.filter(
    (step) => notice.sandbox || step.phase === "starting-kernel",
  ).map(({ phase, titles, descriptions }) => {
    const preparing = phase === "preparing-environment";
    let state: ProgressState;
    if (notice.ready || (preparing && activePhase === "starting-kernel")) {
      state = "succeeded";
    } else if (activePhase === phase) {
      state = notice.pending ? "running" : "failed";
    } else {
      state = "waiting";
    }
    let logs;
    if (preparing) {
      logs = preparation?.logs.environment ?? "";
    } else if (progress?.phase === phase) {
      logs = progress.logs;
    } else {
      logs = "";
    }
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
