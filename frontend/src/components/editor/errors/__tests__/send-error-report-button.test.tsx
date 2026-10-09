/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { PAIR_PREVIEW } from "@/__tests__/fixtures/pair-preview";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { type Attachment, attachmentsAtom } from "@/core/attachments/state";
import { exportedForTesting, notebookAtom } from "@/core/cells/cells";
import type {
  CellOutputHandoff,
  ErrorHandoffOutput,
} from "@/core/cells/error-report";
import { pairPreviewAtom } from "@/core/config/pair";
import type { MarimoError, OutputMessage } from "@/core/kernel/messages";
import {
  type StableSessionId,
  stableSessionIdAtom,
} from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketClosedReason, WebSocketState } from "@/core/websocket/types";
import { Deferred } from "@/utils/Deferred";
import { HTTPError } from "@/utils/errors";
import { MarimoErrorOutput } from "../../output/MarimoErrorOutput";
import { MarimoTracebackOutput } from "../../output/MarimoTracebackOutput";
import { OutputRenderer } from "../../Output";
import { SendErrorReportButton } from "../send-error-report-button";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));
vi.mock("@/core/network/api", () => ({ API: { post: vi.fn() } }));
vi.mock("@/components/editor/chrome/wrapper/useOpenAiAssistant", () => ({
  useOpenAiAssistant: () => vi.fn(),
}));

const CELL_ID = cellId("test-cell");
const STABLE_ID = "stable/test" as StableSessionId;
const AGENT: Attachment = { id: "a1", kind: "agent", name: "Pi", since: 1 };
const ROUTE = "/pair/notebooks/stable%2Ftest/handoffs";
const MESSAGE = "df is not defined";
const CODE = "df.head()";
const REPORT: CellOutputHandoff<ErrorHandoffOutput> = {
  type: "cell-output",
  cell_id: CELL_ID,
  code: CODE,
  output: { type: "error", message: MESSAGE },
};
const ERRORS: MarimoError[] = [
  {
    type: "exception",
    exception_type: "NameError",
    raising_cell: null,
    msg: MESSAGE,
    traceback: null,
  },
];

function renderButton({
  preview = true,
  attachments = [AGENT],
  stableId = STABLE_ID,
  content = <SendErrorReportButton getContent={() => REPORT} />,
}: {
  preview?: boolean;
  attachments?: Attachment[];
  stableId?: StableSessionId | null;
  content?: React.ReactNode;
} = {}) {
  const store = createStore();
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  store.set(pairPreviewAtom, preview ? PAIR_PREVIEW : undefined);
  store.set(attachmentsAtom, attachments);
  store.set(stableSessionIdAtom, stableId);
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <TooltipProvider>{children}</TooltipProvider>
    </Provider>
  );
  return { store, ...render(content, { wrapper }) };
}

function send() {
  fireEvent.click(screen.getByRole("button", { name: "Send error to agent" }));
}

describe("SendErrorReportButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(API.post).mockResolvedValue("");
  });

  it("hides outside the preview without building content", () => {
    const getContent = vi.fn(() => REPORT);
    expect(
      renderButton({
        preview: false,
        content: <SendErrorReportButton getContent={getContent} />,
      }).container,
    ).toBeEmptyDOMElement();
    expect(getContent).not.toHaveBeenCalled();
  });

  it.each([
    { attachments: [] },
    { attachments: [{ ...AGENT, kind: "client" as const }] },
    { stableId: null },
  ])("disables sending without an agent or stable ID: %j", (options) => {
    renderButton(options);
    expect(screen.getByRole("button")).toBeDisabled();
    send();
    expect(API.post).not.toHaveBeenCalled();
  });

  it("builds content on click and sends it to all agents", async () => {
    const getContent = vi.fn(() => REPORT);
    renderButton({
      attachments: [AGENT, { ...AGENT, id: "a2", name: "Claude Code" }],
      content: <SendErrorReportButton getContent={getContent} />,
    });
    expect(getContent).not.toHaveBeenCalled();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({ title: "Sent to Pi, Claude Code" }),
    );
    expect(API.post).toHaveBeenCalledWith(ROUTE, REPORT);
    expect(getContent).toHaveBeenCalledOnce();
  });

  it("prevents duplicate sends while a request is pending", async () => {
    const deferred = new Deferred<string>();
    vi.mocked(API.post).mockReturnValue(deferred.promise);
    renderButton();
    send();
    expect(screen.getByRole("button")).toBeDisabled();
    send();
    expect(API.post).toHaveBeenCalledOnce();
    await act(async () => deferred.resolve(""));
    expect(screen.getByRole("button")).toBeEnabled();
  });

  it("disables the button after the last agent disconnects", () => {
    const { store } = renderButton();
    act(() => store.set(attachmentsAtom, []));
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it.each([
    { state: WebSocketState.CONNECTING },
    { state: WebSocketState.CLOSING },
    { state: WebSocketState.NOT_STARTED },
    {
      state: WebSocketState.CLOSED,
      code: WebSocketClosedReason.KERNEL_DISCONNECTED,
      reason: "offline",
    },
  ])(
    "does not send from a stale snapshot while the browser is %j",
    (connection) => {
      const { store } = renderButton();
      act(() => store.set(connectionAtom, connection));
      expect(screen.getByRole("button")).toBeDisabled();
      send();
      expect(API.post).not.toHaveBeenCalled();
    },
  );

  it.each([
    [new HTTPError(409, "Conflict"), "No agent attached"],
    [new HTTPError(500, "Server error"), "Could not send error"],
  ])("reports request failures and permits retry", async (error, title) => {
    vi.mocked(API.post).mockRejectedValueOnce(error);
    renderButton();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({ variant: "danger", title }),
    );
    expect(screen.getByRole("button")).toBeEnabled();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({ title: "Sent to Pi" }),
    );
    expect(API.post).toHaveBeenCalledTimes(2);
    expect(API.post).toHaveBeenLastCalledWith(ROUTE, REPORT);
  });

  it("sends captured code and full traceback from the error output", async () => {
    const traceback = "<pre>Traceback\nNameError: df is not defined</pre>";
    renderButton({
      content: (
        <OutputRenderer
          cellId={CELL_ID}
          message={{
            channel: "marimo-error",
            mimetype: "application/vnd.marimo+error",
            code: CODE,
            data: [{ ...ERRORS[0], traceback }],
          }}
        />
      ),
    });
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(ROUTE, {
        ...REPORT,
        output: {
          type: "error",
          message: MESSAGE,
          traceback: "Traceback\nNameError: df is not defined",
        },
      }),
    );
  });

  it("sends a formatter error beside a normal main output", async () => {
    const { store } = renderButton({
      content: (
        <OutputRenderer
          cellId={CELL_ID}
          message={{
            channel: "stderr",
            mimetype: "application/vnd.marimo+traceback",
            code: CODE,
            data: "<pre>Traceback\nValueError: bad &lt;value&gt;</pre>",
          }}
        />
      ),
    });
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [CELL_ID]: { code: "later edit" } },
        cellRuntime: {
          [CELL_ID]: {
            output: {
              channel: "output",
              mimetype: "text/plain",
              data: "<Broken formatter>",
            },
          },
        },
      }),
    );
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(ROUTE, {
        ...REPORT,
        output: {
          type: "error",
          message: "ValueError: bad <value>",
          traceback: "Traceback\nValueError: bad <value>",
        },
      }),
    );
  });

  it("sends updated content after the error changes", async () => {
    const { rerender } = renderButton();
    const updated = {
      ...REPORT,
      output: { type: "error", message: "Another error" },
    };
    rerender(<SendErrorReportButton getContent={() => updated} />);
    send();
    await waitFor(() => expect(API.post).toHaveBeenCalledWith(ROUTE, updated));
  });

  it.each([
    "Hello agent",
    { lens: { selection: [1, 2], chart: "scatter" } },
    [1, "two"],
    null,
  ])("accepts arbitrary producer content: %j", async (content) => {
    renderButton({
      content: <SendErrorReportButton getContent={() => content} />,
    });
    send();
    await waitFor(() => expect(API.post).toHaveBeenCalledWith(ROUTE, content));
  });

  it.each([false, true])(
    "retains failed code after edits and a queued run (%s)",
    async (queue) => {
      const output: OutputMessage = {
        channel: "marimo-error",
        mimetype: "application/vnd.marimo+error",
        data: ERRORS,
        code: CODE,
      };
      const { store } = renderButton({
        content: <OutputRenderer cellId={CELL_ID} message={output} />,
      });
      store.set(
        notebookAtom,
        MockNotebook.notebookState({
          cellData: { [CELL_ID]: { code: CODE, lastCodeRun: CODE } },
          cellRuntime: { [CELL_ID]: { output } },
        }),
      );
      const actions = exportedForTesting.createActions((action) => {
        store.set(notebookAtom, (state) =>
          exportedForTesting.reducer(state, action),
        );
      });
      act(() => {
        actions.updateCellCode({
          cellId: CELL_ID,
          code: "print('edited')",
          formattingChange: false,
        });
        if (queue) {
          actions.prepareForRun({ cellId: CELL_ID });
          actions.handleCellMessage({
            cell_id: CELL_ID,
            status: "queued",
            timestamp: 2,
          });
        }
      });
      send();
      await waitFor(() => expect(API.post).toHaveBeenCalledWith(ROUTE, REPORT));
    },
  );

  it("does not borrow an old console traceback for a cancelled descendant", async () => {
    const cancelled: MarimoError[] = [
      {
        type: "exception",
        exception_type: "ValueError",
        msg: "Ancestor failed",
        raising_cell: cellId("ancestor"),
        traceback: null,
      },
    ];
    const { store } = renderButton({
      content: (
        <MarimoErrorOutput cellId={CELL_ID} code="x + 1" errors={cancelled} />
      ),
    });
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: {
          [CELL_ID]: { code: "unrelated edit", lastCodeRun: "older run" },
        },
        cellRuntime: {
          [CELL_ID]: {
            consoleOutputs: [
              {
                channel: "stderr",
                mimetype: "application/vnd.marimo+traceback",
                data: "<pre>Old unrelated traceback</pre>",
                code: "older run",
              },
            ],
          },
        },
      }),
    );
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(ROUTE, {
        type: "cell-output",
        cell_id: CELL_ID,
        code: "x + 1",
        output: { type: "error", message: "Ancestor failed" },
      }),
    );
  });

  it("sends an interruption with its attempted code", async () => {
    renderButton({
      content: (
        <MarimoErrorOutput
          cellId={CELL_ID}
          code="slow()"
          errors={[{ type: "interruption" }]}
        />
      ),
    });
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(ROUTE, {
        type: "cell-output",
        cell_id: CELL_ID,
        code: "slow()",
        output: {
          type: "error",
          message: "This cell was interrupted and needs to be re-run",
        },
      }),
    );
  });

  it("hides error actions without a cell identity or message", () => {
    renderButton({
      content: (
        <>
          <MarimoErrorOutput cellId={undefined} errors={ERRORS} />
          <MarimoErrorOutput cellId={CELL_ID} errors={[]} />
          <MarimoTracebackOutput
            cellId={undefined}
            traceback="<pre>ValueError: bad</pre>"
          />
        </>
      ),
    });
    expect(
      screen.queryByRole("button", { name: "Send error to agent" }),
    ).not.toBeInTheDocument();
  });
});
