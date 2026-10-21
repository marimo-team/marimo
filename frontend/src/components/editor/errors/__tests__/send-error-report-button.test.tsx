/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { atom, createStore, Provider, useAtomValue } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { SendResult } from "@/core/agents/messages";
import { toast } from "@/components/ui/use-toast";
import type { Attachment } from "@/core/notebook/attachments";
import { exportedForTesting, notebookAtom } from "@/core/cells/cells";
import {
  type CellOutputMessage,
  type ErrorMessageOutput,
  ERROR_MESSAGE_INSTRUCTIONS,
} from "@/core/cells/error-report";
import { readExport } from "@/core/cells/session";
import type { MarimoError, OutputMessage } from "@/core/kernel/messages";
import {
  type StableSessionId,
  stableSessionIdAtom,
} from "@/core/kernel/session";
import { type AppMode, initialModeAtom, viewStateAtom } from "@/core/mode";
import { API } from "@/core/network/api";
import { connectionAtom } from "@/core/network/connection";
import { ConnectionState } from "@/core/session/types";
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
const attachmentsAtom = atom<Attachment[]>([]);
vi.mock("@/core/session/active-notebook", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/session/active-notebook")>()),
  activeNotebookReplicaAtom: atom(() => ({ attachmentsAtom })),
}));

const AGENT: Attachment = {
  id: "a1",
  kind: "agent",
  name: "Pi",
  since: "2026-10-14T00:00:00Z",
  notebook_id: "nb-test",
  identity: "pi-thread",
};
const ROUTE = "/pair/notebooks/stable%2Ftest/messages";
const SUBMITTED: SendResult = {
  recipients: [{ agent_id: "pi-thread", status: "submitted", detail: null }],
};
const requestFor = (message: unknown) => ({ message, to: "pi-thread" });
const MESSAGE = "df is not defined";
const CODE = "df.head()";
const REPORT: CellOutputMessage<ErrorMessageOutput> = {
  type: "cell-output",
  cell_id: CELL_ID,
  code: CODE,
  output: {
    type: "error",
    instructions: ERROR_MESSAGE_INSTRUCTIONS,
    message: MESSAGE,
  },
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
  mode = "edit",
  attachments = [AGENT],
  stableId = STABLE_ID,
  content = <SendErrorReportButton getContent={() => REPORT} />,
}: {
  mode?: AppMode;
  attachments?: Attachment[];
  stableId?: StableSessionId | null;
  content?: React.ReactNode;
} = {}) {
  const store = createStore();
  store.set(connectionAtom, { state: ConnectionState.OPEN });
  store.set(initialModeAtom, mode);
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
    vi.mocked(API.post).mockResolvedValue(SUBMITTED);
    vi.mocked(toast).mockReturnValue({
      id: "notice",
      dismiss: vi.fn(),
      update: vi.fn(),
      upsert: vi.fn(),
    });
  });

  it("hides in read mode without building content", () => {
    const getContent = vi.fn(() => REPORT);
    expect(
      renderButton({
        mode: "read",
        content: <SendErrorReportButton getContent={getContent} />,
      }).container,
    ).toBeEmptyDOMElement();
    expect(getContent).not.toHaveBeenCalled();
  });

  it("remains available when an editor enters presentation mode", () => {
    const { store } = renderButton();
    act(() => store.set(viewStateAtom, { mode: "present", cellAnchor: null }));
    expect(screen.getByRole("button")).toBeEnabled();
  });

  it.each([
    { attachments: [] },
    { attachments: [{ ...AGENT, kind: "client" as const }] },
  ])("hides without a connected agent: %j", (options) => {
    const getContent = vi.fn(() => REPORT);
    const { container } = renderButton({
      ...options,
      content: <SendErrorReportButton getContent={getContent} />,
    });
    expect(container).toBeEmptyDOMElement();
    expect(getContent).not.toHaveBeenCalled();
    expect(API.post).not.toHaveBeenCalled();
  });

  it("disables sending without a stable ID", () => {
    renderButton({ stableId: null });
    expect(screen.getByRole("button")).toBeDisabled();
    send();
    expect(API.post).not.toHaveBeenCalled();
  });

  it("groups reconnecting attachments and sends to the logical agent", async () => {
    const getContent = vi.fn(() => REPORT);
    renderButton({
      attachments: [AGENT, { ...AGENT, id: "a2", name: "Claude Code" }],
      content: <SendErrorReportButton getContent={getContent} />,
    });
    expect(getContent).not.toHaveBeenCalled();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: "Submitted to Claude Code",
        duration: 3000,
      }),
    );
    expect(API.post).toHaveBeenCalledWith(
      ROUTE,
      requestFor(REPORT),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(getContent).toHaveBeenCalledOnce();
  });

  it("prevents duplicate sends while a request is pending", async () => {
    const deferred = new Deferred<SendResult>();
    vi.mocked(API.post).mockReturnValue(deferred.promise);
    renderButton();
    send();
    expect(screen.getByRole("button")).toBeDisabled();
    send();
    expect(API.post).toHaveBeenCalledOnce();
    await act(async () => deferred.resolve(SUBMITTED));
    expect(screen.getByRole("button")).toBeEnabled();
  });

  it("offers distinct recipients and explicit broadcast through the keyboard", async () => {
    renderButton({
      attachments: [AGENT, { ...AGENT, id: "a2", identity: "another-thread" }],
    });
    fireEvent.keyDown(screen.getByRole("button"), { key: "ArrowDown" });
    const target = await screen.findByRole("menuitem", {
      name: "Pi (another-thread)",
    });
    expect(
      screen.getByRole("menuitem", { name: "Pi (pi-thread)" }),
    ).toBeVisible();
    expect(
      screen.getByRole("menuitem", { name: "Send to all agents" }),
    ).toBeVisible();
    expect(API.post).not.toHaveBeenCalled();
    fireEvent.click(target);
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        { message: REPORT, to: "another-thread" },
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
  });

  it("broadcasts only after an explicit choice and reports partial outcomes", async () => {
    vi.mocked(API.post).mockResolvedValue({
      recipients: [
        { agent_id: "pi-thread", status: "submitted", detail: null },
        {
          agent_id: "claude",
          status: "unknown",
          detail: "No native acceptance receipt",
        },
      ],
    });
    renderButton({
      attachments: [
        AGENT,
        { ...AGENT, id: "a2", identity: "claude", name: "Claude" },
      ],
    });
    fireEvent.keyDown(screen.getByRole("button"), { key: "ArrowDown" });
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Send to all agents" }),
    );
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        { message: REPORT, broadcast: true },
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: "danger",
          title: "Some messages were not confirmed",
          description: expect.stringContaining(
            "Claude: No native acceptance receipt",
          ),
        }),
      ),
    );
    expect(API.post).toHaveBeenCalledOnce();
  });

  it.each(["rejected", "unknown"])(
    "reports a %s recipient without another send",
    async (status) => {
      vi.mocked(API.post).mockResolvedValue({
        recipients: [{ agent_id: "pi-thread", status, detail: "Disconnected" }],
      });
      renderButton();
      send();
      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: "danger",
            title:
              status === "unknown"
                ? "Submission outcome unknown"
                : "Message rejected",
          }),
        ),
      );
      expect(API.post).toHaveBeenCalledOnce();
      expect(screen.getByRole("button")).toBeEnabled();
    },
  );

  it("retains the chosen target while attachment state changes", async () => {
    const deferred = new Deferred<SendResult>();
    vi.mocked(API.post).mockReturnValue(deferred.promise);
    const { store } = renderButton();
    send();
    act(() =>
      store.set(attachmentsAtom, [{ ...AGENT, id: "a2", identity: "other" }]),
    );
    expect(API.post).toHaveBeenCalledOnce();
    expect(API.post).toHaveBeenCalledWith(
      ROUTE,
      requestFor(REPORT),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    await act(async () => deferred.resolve(SUBMITTED));
    expect(API.post).toHaveBeenCalledOnce();
  });

  it("releases pending state after a producer error without dispatch", async () => {
    renderButton({
      content: (
        <SendErrorReportButton
          getContent={() => {
            throw new Error("Cannot capture output");
          }}
        />
      ),
    });
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Could not send message" }),
      ),
    );
    expect(API.post).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).toBeEnabled();
  });

  it("shows and hides the button as agents connect and disconnect", () => {
    const { store } = renderButton({ attachments: [] });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(screen.getByRole("button")).toBeEnabled();
    act(() =>
      store.set(attachmentsAtom, [
        AGENT,
        { ...AGENT, id: "a2", name: "Claude Code" },
      ]),
    );
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(screen.getByRole("button")).toBeEnabled();
    act(() => store.set(attachmentsAtom, []));
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it.each([
    [
      new HTTPError(409, "Conflict", {
        code: "no-agents",
        detail: "No agents are connected",
      }),
      "Could not send message",
      "No agents are connected",
    ],
    [
      new HTTPError(500, "Server error"),
      "Submission outcome unknown",
      "The submission outcome is unknown. Another send can duplicate the message.",
    ],
  ])(
    "reports request failures and permits retry",
    async (error, title, description) => {
      vi.mocked(API.post).mockRejectedValueOnce(error);
      renderButton();
      send();
      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith({
          variant: "danger",
          title,
          description,
          duration: 5000,
        }),
      );
      expect(screen.getByRole("button")).toBeEnabled();
      send();
      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith({
          title: "Submitted to Pi",
          duration: 3000,
        }),
      );
      expect(API.post).toHaveBeenCalledTimes(2);
      expect(API.post).toHaveBeenLastCalledWith(
        ROUTE,
        requestFor(REPORT),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    },
  );

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
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor({
          ...REPORT,
          output: {
            type: "error",
            instructions: ERROR_MESSAGE_INSTRUCTIONS,
            message: MESSAGE,
            traceback: "Traceback\nNameError: df is not defined",
          },
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
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
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor({
          ...REPORT,
          output: {
            type: "error",
            instructions: ERROR_MESSAGE_INSTRUCTIONS,
            message: "ValueError: bad <value>",
            traceback: "Traceback\nValueError: bad <value>",
          },
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
  });

  it("sends plain code-mode traceback text without parsing it as HTML", async () => {
    const traceback =
      '  File "<cell>", line 1\nValueError: bad <value> & <other>';
    renderButton({
      content: (
        <OutputRenderer
          cellId={CELL_ID}
          message={{
            channel: "stderr",
            mimetype: "application/vnd.marimo+traceback",
            traceback_format: "text",
            code: CODE,
            data: traceback,
          }}
        />
      ),
    });
    expect(screen.getByText(/ValueError: bad <value>/)).toHaveTextContent(
      "<cell>",
    );
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor({
          ...REPORT,
          output: {
            type: "error",
            instructions: ERROR_MESSAGE_INSTRUCTIONS,
            message: "ValueError: bad <value> & <other>",
            traceback,
          },
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
  });

  it("sends the restored exception type and complete traceback", async () => {
    const { cellRuntime } = readExport({
      session: {
        version: "1",
        metadata: { marimo_version: "1", script_metadata_hash: null },
        cells: [
          {
            id: CELL_ID,
            code_hash: null,
            console: [],
            outputs: [
              {
                type: "error",
                ename: "ValueError",
                evalue: "cached failure",
                traceback: [
                  "<pre>Traceback",
                  "  failed()\n",
                  "ValueError: cached failure</pre>",
                ],
                code: CODE,
              },
            ],
          },
        ],
      },
      notebook: null,
      filename: null,
      appConfig: {},
    });
    const message = cellRuntime[CELL_ID].output;
    expect(message).toBeDefined();
    renderButton({
      content: message && <OutputRenderer cellId={CELL_ID} message={message} />,
    });
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor({
          ...REPORT,
          output: {
            type: "error",
            instructions: ERROR_MESSAGE_INSTRUCTIONS,
            message: "cached failure",
            traceback: "Traceback\n  failed()\nValueError: cached failure",
          },
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
    expect(message?.data).toEqual([
      expect.objectContaining({ exception_type: "ValueError" }),
    ]);
  });

  it("sends updated content after the error changes", async () => {
    const { rerender } = renderButton();
    const updated = {
      ...REPORT,
      output: { type: "error", message: "Another error" },
    };
    rerender(<SendErrorReportButton getContent={() => updated} />);
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor(updated),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
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
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor(content),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
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
      // Render from the store so reducer changes reach the button.
      const StoreOutput = () => {
        const message = useAtomValue(notebookAtom).cellRuntime[CELL_ID]?.output;
        return message ? (
          <OutputRenderer cellId={CELL_ID} message={message} />
        ) : null;
      };
      const { store } = renderButton({ content: <StoreOutput /> });
      const actions = exportedForTesting.createActions((action) => {
        store.set(notebookAtom, (state) =>
          exportedForTesting.reducer(state, action),
        );
      });
      act(() => {
        store.set(
          notebookAtom,
          MockNotebook.notebookState({
            cellData: { [CELL_ID]: { code: CODE } },
            cellRuntime: { [CELL_ID]: { output } },
          }),
        );
        store.set(notebookAtom, (state) => ({
          ...state,
          cellData: {
            ...state.cellData,
            [CELL_ID]: {
              ...state.cellData[CELL_ID],
              code: "print('edited')",
            },
          },
        }));
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
      await waitFor(() =>
        expect(API.post).toHaveBeenCalledWith(
          ROUTE,
          requestFor(REPORT),
          expect.objectContaining({ signal: expect.any(AbortSignal) }),
        ),
      );
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
          [CELL_ID]: { code: "unrelated edit" },
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
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor({
          type: "cell-output",
          cell_id: CELL_ID,
          code: "x + 1",
          output: {
            type: "error",
            instructions: ERROR_MESSAGE_INSTRUCTIONS,
            message: "Ancestor failed",
          },
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
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
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        requestFor({
          type: "cell-output",
          cell_id: CELL_ID,
          code: "slow()",
          output: {
            type: "error",
            instructions: ERROR_MESSAGE_INSTRUCTIONS,
            message: "This cell was interrupted and needs to be re-run",
          },
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
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
