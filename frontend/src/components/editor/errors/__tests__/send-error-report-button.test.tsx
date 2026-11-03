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
import { initialModeAtom } from "@/core/mode";
import { API } from "@/core/network/api";
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
  content = <SendErrorReportButton getContent={() => REPORT} />,
}: {
  content?: React.ReactNode;
} = {}) {
  const store = createStore();
  store.set(initialModeAtom, "edit");
  store.set(attachmentsAtom, [AGENT]);
  store.set(stableSessionIdAtom, STABLE_ID);
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
