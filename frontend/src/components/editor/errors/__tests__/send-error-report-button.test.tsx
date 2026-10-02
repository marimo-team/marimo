/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { PAIR_PREVIEW } from "@/__tests__/fixtures/pair-preview";
import { MockNotebook } from "@/__mocks__/notebook";
import { toast } from "@/components/ui/use-toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import { notebookAtom } from "@/core/cells/cells";
import type { CellRuntimeState } from "@/core/cells/types";
import { pairPreviewAtom } from "@/core/config/pair";
import { API } from "@/core/network/api";
import {
  type ParticipantPresence,
  participantPresenceAtom,
} from "@/core/participants/state";
import { SendErrorReportButton } from "../send-error-report-button";
import { MarimoErrorOutput } from "../../output/MarimoErrorOutput";
import { MarimoTracebackOutput } from "../../output/MarimoTracebackOutput";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));
vi.mock("@/core/network/api", () => ({ API: { post: vi.fn() } }));
vi.mock("@/components/editor/chrome/wrapper/useOpenAiAssistant", () => ({
  useOpenAiAssistant: () => vi.fn(),
}));

const CELL_ID = cellId("test-cell");
const CONNECTED: ParticipantPresence = {
  op: "participant-presence",
  active: false,
  active_since: null,
  attached: true,
  harness: { id: "pi", displayName: "Pi" },
  kind: "agent",
  last_contact_at: 1,
  listening: false,
  participant_id: "participant-1",
};

function renderButton({
  preview = true,
  presence = CONNECTED,
  preferLastRunCode = false,
  consoleTraceback = '<span class="codehilite"><pre><span class="gr">third</span></pre></span>',
  consoleOutputs,
  content,
}: {
  preview?: boolean;
  presence?: ParticipantPresence | null;
  preferLastRunCode?: boolean;
  consoleTraceback?: string;
  consoleOutputs?: CellRuntimeState["consoleOutputs"];
  content?: React.ReactNode;
} = {}) {
  const store = createStore();
  store.set(pairPreviewAtom, preview ? PAIR_PREVIEW : undefined);
  store.set(participantPresenceAtom, presence);
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: {
        [CELL_ID]: { code: "current_code()", lastCodeRun: "failed_code()" },
      },
      cellRuntime: {
        [CELL_ID]: {
          consoleOutputs: consoleOutputs ?? [
            {
              channel: "stdout",
              data: "first\nsecond",
              mimetype: "text/plain",
            },
            {
              channel: "stderr",
              data: consoleTraceback,
              mimetype: "application/vnd.marimo+traceback",
            },
            {
              channel: "stdout",
              data: "<span>fourth</span>",
              mimetype: "text/html",
            },
          ],
        },
      },
    }),
  );
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <TooltipProvider>{children}</TooltipProvider>
    </Provider>
  );
  return render(
    content ?? (
      <SendErrorReportButton
        cellId={CELL_ID}
        error="NameError: df is not defined"
        traceback={"<pre>Traceback\nNameError: df is not defined</pre>"}
        preferLastRunCode={preferLastRunCode}
      />
    ),
    { wrapper },
  );
}

describe("SendErrorReportButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is hidden unless the preview channel has an attached participant", () => {
    expect(renderButton({ preview: false }).container).toBeEmptyDOMElement();
    expect(renderButton({ presence: null }).container).toBeEmptyDOMElement();
    expect(
      renderButton({ presence: { ...CONNECTED, attached: false } }).container,
    ).toBeEmptyDOMElement();
  });

  it("appears in both error output types and sends current code for static errors", async () => {
    vi.mocked(API.post).mockResolvedValue({ seq: 1 });
    renderButton({
      content: (
        <MarimoErrorOutput
          cellId={CELL_ID}
          errors={[MockNotebook.errors.syntax("invalid syntax")]}
        />
      ),
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );
    await waitFor(() => {
      expect(API.post).toHaveBeenCalledWith(
        "/participants/handoff",
        expect.objectContaining({
          error: "invalid syntax",
          code: "current_code()",
          traceback: "",
        }),
      );
    });

    renderButton({
      content: (
        <MarimoTracebackOutput
          cellId={CELL_ID}
          traceback="<pre>Traceback</pre>"
        />
      ),
    });
    expect(
      screen.getAllByRole("button", { name: "Send error to agent" }),
    ).toHaveLength(2);
  });

  it("sends the failed code and error evidence, then names the recipient", async () => {
    vi.mocked(API.post).mockResolvedValue({ seq: 1 });
    renderButton({ preferLastRunCode: true });

    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );

    await waitFor(() => {
      expect(API.post).toHaveBeenCalledWith("/participants/handoff", {
        cellId: CELL_ID,
        error: "NameError: df is not defined",
        code: "failed_code()",
        traceback: "Traceback\nNameError: df is not defined",
        consoleTail: [
          { channel: "stdout", data: "first" },
          { channel: "stdout", data: "second" },
          { channel: "stdout", data: "fourth" },
        ],
      });
      expect(toast).toHaveBeenCalledWith({ title: "Sent to Pi" });
    });
  });

  it("uses the matching console traceback for an exception summary", async () => {
    vi.mocked(API.post).mockResolvedValue({ seq: 1 });
    renderButton({
      consoleTraceback:
        '<span class="codehilite"><pre>Traceback\nException: Something went wrong!</pre></span>',
      content: (
        <MarimoErrorOutput
          cellId={CELL_ID}
          errors={[
            MockNotebook.errors.exception("Something went wrong!", "Exception"),
          ]}
        />
      ),
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );

    await waitFor(() => {
      expect(API.post).toHaveBeenCalledWith(
        "/participants/handoff",
        expect.objectContaining({
          error: "Exception: Something went wrong!",
          code: "failed_code()",
          traceback: "Traceback\nException: Something went wrong!",
          consoleTail: [
            { channel: "stdout", data: "first" },
            { channel: "stdout", data: "second" },
            { channel: "stdout", data: "fourth" },
          ],
        }),
      );
    });
  });

  it("matches one exception in a summary with multiple errors", async () => {
    vi.mocked(API.post).mockResolvedValue({ seq: 1 });
    renderButton({
      consoleTraceback:
        "<pre>Traceback\nException: Something went wrong!</pre>",
      content: (
        <MarimoErrorOutput
          cellId={CELL_ID}
          errors={[
            MockNotebook.errors.syntax("invalid syntax"),
            MockNotebook.errors.exception("Something went wrong!", "Exception"),
          ]}
        />
      ),
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );

    await waitFor(() => {
      expect(API.post).toHaveBeenCalledWith(
        "/participants/handoff",
        expect.objectContaining({
          error: "invalid syntax\nException: Something went wrong!",
          traceback: "Traceback\nException: Something went wrong!",
        }),
      );
    });
  });

  it("keeps recent console content within the handoff byte limit", async () => {
    vi.mocked(API.post).mockResolvedValue({ seq: 1 });
    renderButton({
      consoleOutputs: [
        {
          channel: "stderr",
          data: `\n${"x".repeat(300_000)}\nuseful detail`,
          mimetype: "text/plain",
        },
      ],
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );

    await waitFor(() => expect(API.post).toHaveBeenCalledOnce());
    const sent = vi.mocked(API.post).mock.calls[0]?.[1];
    expect(sent).toEqual(
      expect.objectContaining({
        consoleTail: expect.arrayContaining([
          { channel: "stderr", data: "useful detail" },
        ]),
      }),
    );
    expect(new TextEncoder().encode(JSON.stringify(sent)).length).toBeLessThan(
      256 * 1024,
    );
  });

  it("shows a size error when the code alone exceeds the request limit", async () => {
    const store = createStore();
    store.set(pairPreviewAtom, PAIR_PREVIEW);
    store.set(participantPresenceAtom, CONNECTED);
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [CELL_ID]: { code: "x".repeat(300_000) },
        },
      }),
    );
    render(
      <Provider store={store}>
        <SendErrorReportButton
          cellId={CELL_ID}
          error="NameError"
          traceback=""
        />
      </Provider>,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith({
        variant: "danger",
        title: "Error report is too large to send",
      });
    });
    expect(API.post).not.toHaveBeenCalled();
  });

  it("includes cells and variables in cross-cell error handoffs", async () => {
    vi.mocked(API.post).mockResolvedValue({ seq: 1 });
    renderButton({
      content: (
        <MarimoErrorOutput
          cellId={CELL_ID}
          errors={[
            {
              type: "setup-refs",
              edges_with_vars: [[cellId("source"), ["x"], CELL_ID]],
            },
            {
              type: "cycle",
              edges_with_vars: [[CELL_ID, ["y"], cellId("other")]],
            },
          ]}
        />
      ),
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );

    await waitFor(() => {
      expect(API.post).toHaveBeenCalledWith(
        "/participants/handoff",
        expect.objectContaining({
          error:
            "Setup cell references: source: x\nCycle: test-cell -> y -> other",
        }),
      );
    });
  });

  it("reports a failed send without claiming delivery", async () => {
    vi.mocked(API.post).mockRejectedValue(new Error("No participant"));
    renderButton();

    fireEvent.click(
      screen.getByRole("button", { name: "Send error to agent" }),
    );

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith({
        variant: "danger",
        title: "Could not send error report",
      });
    });
    expect(toast).not.toHaveBeenCalledWith({ title: "Sent to Pi" });
  });
});
