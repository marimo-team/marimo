/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { PAIR_CONFIG } from "@/__tests__/fixtures/pair-config";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import type { Attachment } from "@/core/notebook/attachments";
import { notebookAtom } from "@/core/cells/cells";
import {
  type CellOutputMessage,
  type ErrorMessageOutput,
  ERROR_MESSAGE_INSTRUCTIONS,
} from "@/core/cells/error-report";
import { pairConfigAtom } from "@/core/config/pair";
import { readExport } from "@/core/cells/session";
import { cellOutputView, useCellOutput } from "@/core/executions";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import type { MarimoError } from "@/core/kernel/messages";
import {
  type StableSessionId,
  stableSessionIdAtom,
} from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { viewStateAtom } from "@/core/mode";
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
// Hoisted with the module mock below, which reads it as modules load.
const { attachmentsAtom } = await vi.hoisted(async () => {
  const { atom } = await import("jotai");
  return { attachmentsAtom: atom<Attachment[]>([]) };
});
vi.mock("@/core/session/active-notebook", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/session/active-notebook")>()),
  // Writable, so the execution mock can give the replica results.
  activeNotebookReplicaAtom: atom({ attachmentsAtom }),
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
  store.set(connectionAtom, { state: ConnectionState.OPEN });
  store.set(pairConfigAtom, { ...PAIR_CONFIG, hostEnabled: preview });
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
    vi.mocked(API.post).mockResolvedValue({
      message_id: "m",
      recipients: [
        {
          agent_id: "a",
          name: "Pi",
          status: "submitted",
          reason: null,
          detail: null,
        },
      ],
    });
    vi.mocked(toast).mockReturnValue({
      id: "notice",
      dismiss: vi.fn(),
      update: vi.fn(),
      upsert: vi.fn(),
    });
  });

  it("shows each recipient outcome from the producer", async () => {
    vi.mocked(API.post).mockResolvedValue({
      message_id: "m",
      recipients: [
        {
          agent_id: "one",
          name: "Codex",
          status: "submitted",
          reason: null,
          detail: null,
        },
        {
          agent_id: "two",
          name: "Claude Code",
          status: "unknown",
          reason: "unconfirmed",
          detail: null,
        },
      ],
    });
    renderButton();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Agent message outcomes",
          description:
            "Submitted to Codex\nSent to Claude Code; acceptance unconfirmed",
        }),
      ),
    );
    expect(toast).toHaveBeenCalledOnce();
    expect(API.post).toHaveBeenCalledWith(
      ROUTE,
      expect.objectContaining({
        message_id: expect.any(String),
        message: REPORT,
        sender: "marimo error report",
        broadcast: true,
      }),
    );
  });

  it.each([
    ["rejected", "not-connected"],
    ["rejected", "disconnected"],
    ["rejected", "timeout"],
    ["rejected", "refused"],
    ["rejected", "invalid"],
    ["unknown", "timeout"],
    ["unknown", "disconnected"],
    ["unknown", "failed"],
  ])("shows %s with reason %s", async (status, reason) => {
    vi.mocked(API.post).mockResolvedValue({
      message_id: "m",
      recipients: [
        { agent_id: "a", name: null, status, reason, detail: "More detail" },
      ],
    });
    renderButton();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        title: `a: ${status} (${reason})`,
        description: "More detail",
        duration: 3000,
      }),
    );
  });

  it("hides when host is disabled without building content", () => {
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
  ])("hides without a connected agent: %j", (options) => {
    const getContent = vi.fn(() => REPORT);
    renderButton({
      ...options,
      content: <SendErrorReportButton getContent={getContent} />,
    });
    expect(
      screen.queryByRole("button", { name: "Send error to agent" }),
    ).not.toBeInTheDocument();
    expect(getContent).not.toHaveBeenCalled();
    expect(API.post).not.toHaveBeenCalled();
  });

  it("disables sending without a stable session ID", () => {
    renderButton({ stableId: null });
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
      expect(toast).toHaveBeenCalledWith({
        title: "Submitted to Pi",
        duration: 3000,
      }),
    );
    expect(API.post).toHaveBeenCalledWith(
      ROUTE,
      expect.objectContaining({
        message_id: expect.any(String),
        broadcast: true,
        message: REPORT,
      }),
    );
    expect(getContent).toHaveBeenCalledOnce();
  });

  describe("with several agents", () => {
    const CODEX: Attachment = {
      ...AGENT,
      id: "a2",
      name: "Codex",
      identity: "codex-thread",
    };

    function openMenu() {
      fireEvent.keyDown(
        screen.getByRole("button", { name: "Send error to agent" }),
        { key: "Enter" },
      );
    }

    it("marks the button as a menu only when a choice exists", () => {
      const chevron = () =>
        screen
          .getByRole("button", { name: "Send error to agent" })
          .querySelector(".lucide-chevron-down");
      const { store } = renderButton({ attachments: [AGENT, CODEX] });
      expect(chevron()).toBeInTheDocument();
      act(() => store.set(attachmentsAtom, [AGENT]));
      expect(chevron()).not.toBeInTheDocument();
    });

    it("offers each agent and a broadcast without sending", async () => {
      const getContent = vi.fn(() => REPORT);
      renderButton({
        attachments: [AGENT, CODEX],
        content: <SendErrorReportButton getContent={getContent} />,
      });
      openMenu();
      const items = await screen.findAllByRole("menuitem");
      expect(items.map((item) => item.textContent)).toEqual([
        "Pi",
        "Codex",
        "Send to all agents",
      ]);
      expect(getContent).not.toHaveBeenCalled();
      expect(API.post).not.toHaveBeenCalled();
    });

    it("sends to the selected agent only", async () => {
      renderButton({ attachments: [AGENT, CODEX] });
      openMenu();
      fireEvent.click(await screen.findByRole("menuitem", { name: "Codex" }));
      await waitFor(() => expect(API.post).toHaveBeenCalledOnce());
      const body = vi.mocked(API.post).mock.calls[0][1];
      expect(body).toMatchObject({ to: "codex-thread", message: REPORT });
      expect(body).not.toHaveProperty("broadcast");
    });

    it("broadcasts on request", async () => {
      renderButton({ attachments: [AGENT, CODEX] });
      openMenu();
      fireEvent.click(
        await screen.findByRole("menuitem", { name: "Send to all agents" }),
      );
      await waitFor(() => expect(API.post).toHaveBeenCalledOnce());
      const body = vi.mocked(API.post).mock.calls[0][1];
      expect(body).toMatchObject({ broadcast: true, message: REPORT });
      expect(body).not.toHaveProperty("to");
    });

    it("tells agents with the same name apart", async () => {
      vi.mocked(API.post).mockResolvedValue({
        message_id: "m",
        recipients: [
          {
            agent_id: "p1_bbbbbb222222",
            name: "Claude Code",
            status: "submitted",
            reason: null,
            detail: null,
          },
        ],
      });
      renderButton({
        attachments: [
          { ...AGENT, name: "Claude Code", identity: "p1_aaaaaa111111" },
          { ...CODEX, name: "Claude Code", identity: "p1_bbbbbb222222" },
        ],
      });
      openMenu();
      const second = await screen.findByRole("menuitem", {
        name: "Claude Code (222222)",
      });
      expect(
        screen.getByRole("menuitem", { name: "Claude Code (111111)" }),
      ).toBeInTheDocument();
      fireEvent.click(second);
      await waitFor(() =>
        expect(toast).toHaveBeenCalledWith({
          title: "Submitted to Claude Code (222222)",
          duration: 3000,
        }),
      );
      expect(vi.mocked(API.post).mock.calls[0][1]).toMatchObject({
        to: "p1_bbbbbb222222",
      });
    });
  });

  it("makes a new UUID before each request", async () => {
    const ids: string[] = [];
    vi.mocked(API.post).mockImplementation(async (_route, body) => {
      if (
        body == null ||
        typeof body !== "object" ||
        !("message_id" in body) ||
        typeof body.message_id !== "string"
      ) {
        throw new Error("Expected a message with a Message ID");
      }
      const { message_id } = body;
      expect(message_id).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
      );
      ids.push(message_id);
      return { message_id, recipients: [] };
    });
    renderButton();
    send();
    await waitFor(() => expect(screen.getByRole("button")).toBeEnabled());
    send();
    await waitFor(() => expect(ids).toHaveLength(2));
    expect(ids[0]).not.toBe(ids[1]);
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

  it("appears on connection and hides after the last agent disconnects", () => {
    const { store } = renderButton({ attachments: [] });
    expect(
      screen.queryByRole("button", { name: "Send error to agent" }),
    ).not.toBeInTheDocument();
    act(() => store.set(attachmentsAtom, [AGENT]));
    expect(
      screen.getByRole("button", { name: "Send error to agent" }),
    ).toBeEnabled();
    act(() => store.set(attachmentsAtom, []));
    expect(
      screen.queryByRole("button", { name: "Send error to agent" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    [new HTTPError(409, "Conflict"), "Could not send error"],
    [new HTTPError(500, "Server error"), "Could not send error"],
  ])("reports request failures and permits retry", async (error, title) => {
    vi.mocked(API.post).mockRejectedValueOnce(error);
    renderButton();
    send();
    await waitFor(() =>
      expect(toast).toHaveBeenCalledWith({
        variant: "danger",
        title,
        description: error.message,
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
      expect.objectContaining({ message: REPORT }),
    );
  });

  it("shows one action for an error with a console traceback", () => {
    const traceback = "<pre>Traceback\nNameError: df is not defined</pre>";
    const { store, rerender } = renderButton({
      content: (
        <>
          <MarimoErrorOutput cellId={CELL_ID} code={CODE} errors={ERRORS} />
          <MarimoTracebackOutput
            cellId={CELL_ID}
            code={CODE}
            traceback={traceback}
          />
        </>
      ),
    });
    act(() => {
      store.set(viewStateAtom, { ...store.get(viewStateAtom), mode: "edit" });
      store.set(
        notebookAtom,
        MockNotebook.notebookState({
          cellData: { [CELL_ID]: { code: CODE } },
          cellRuntime: {
            [CELL_ID]: {
              consoleOutputs: [
                {
                  channel: "stderr",
                  mimetype: "application/vnd.marimo+traceback",
                  data: traceback,
                  code: CODE,
                },
              ],
            },
          },
        }),
      );
    });
    expect(
      screen.getAllByRole("button", { name: "Send error to agent" }),
    ).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Collapse traceback" }));
    expect(
      screen.getByRole("button", { name: "Send error to agent" }),
    ).toBeEnabled();

    act(() => store.set(notebookAtom, MockNotebook.notebookState()));
    rerender(
      <MarimoErrorOutput cellId={CELL_ID} code={CODE} errors={ERRORS} />,
    );
    expect(
      screen.getByRole("button", { name: "Send error to agent" }),
    ).toBeEnabled();
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
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: {
            ...REPORT,
            output: {
              type: "error",
              instructions: ERROR_MESSAGE_INSTRUCTIONS,
              message: MESSAGE,
              traceback: "Traceback\nNameError: df is not defined",
            },
          },
        }),
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
      }),
    );
    MockExecutions.seed(store, [
      MockExecutions.shown(CELL_ID, {
        mimetype: "text/plain",
        data: "<Broken formatter>",
      }),
    ]);
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: {
            ...REPORT,
            output: {
              type: "error",
              instructions: ERROR_MESSAGE_INSTRUCTIONS,
              message: "ValueError: bad <value>",
              traceback: "Traceback\nValueError: bad <value>",
            },
          },
        }),
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
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: {
            ...REPORT,
            output: {
              type: "error",
              instructions: ERROR_MESSAGE_INSTRUCTIONS,
              message: "ValueError: bad <value> & <other>",
              traceback,
            },
          },
        }),
      ),
    );
  });

  it("sends the restored exception type and complete traceback", async () => {
    const { snapshot } = readExport({
      session: {
        version: "1",
        metadata: { marimo_version: "1", script_metadata_hash: null },
        cells: [
          {
            id: CELL_ID,
            code_hash: "h",
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
      notebook: {
        version: "1",
        metadata: { marimo_version: "1" },
        cells: [
          { id: CELL_ID, code: CODE, code_hash: "h", name: null, config: {} },
        ],
      },
      filename: null,
      appConfig: {},
    });
    const message = cellOutputView(
      {
        ...MockExecutions.inputs(snapshot?.results ?? []),
        cleared: new Map(),
        cells: new Map(snapshot?.cells.map((cell) => [cell.id, cell])),
      },
      CELL_ID,
    );
    expect(message).not.toBeNull();
    renderButton({
      content: message && <OutputRenderer cellId={CELL_ID} message={message} />,
    });
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: {
            ...REPORT,
            output: {
              type: "error",
              instructions: ERROR_MESSAGE_INSTRUCTIONS,
              message: "cached failure",
              traceback: "Traceback\n  failed()\nValueError: cached failure",
            },
          },
        }),
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
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: updated,
        }),
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
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: content,
        }),
      ),
    );
  });

  it("sends the source that raised while the host still has it", async () => {
    const confirmed = (fingerprint: string) =>
      withCells(
        documentOf(),
        {
          c1: null,
          c2: null,
          [CELL_ID]: cell(CELL_ID, CODE, { code_fingerprint: fingerprint }),
        },
        [CELL_ID],
      );
    // Render from the store so the host's changes reach the button.
    const StoreOutput = () => {
      const message = useCellOutput(CELL_ID);
      return message ? (
        <OutputRenderer cellId={CELL_ID} message={message} />
      ) : null;
    };
    const { store, rerender } = renderButton({ content: <div /> });
    const replica = MockExecutions.seed(
      store,
      [
        MockExecutions.failed(
          CELL_ID,
          { name: "NameError", message: MESSAGE },
          { code_fingerprint: "ran" },
        ),
      ],
      null,
      confirmed("ran"),
    );
    rerender(<StoreOutput />);
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: REPORT,
        }),
      ),
    );

    // Once an edit is confirmed, the source that raised is gone.
    vi.mocked(API.post).mockClear();
    act(() => {
      store.set(replica.documentAtom, confirmed("edited"));
    });
    send();
    await waitFor(() =>
      expect(API.post).toHaveBeenCalledWith(
        ROUTE,
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: {
            ...REPORT,
            code: undefined,
          },
        }),
      ),
    );
  });

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
            embeddedConsole: [
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
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: {
            type: "cell-output",
            cell_id: CELL_ID,
            code: "x + 1",
            output: {
              type: "error",
              instructions: ERROR_MESSAGE_INSTRUCTIONS,
              message: "Ancestor failed",
            },
          },
        }),
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
        expect.objectContaining({
          message_id: expect.any(String),
          broadcast: true,
          message: {
            type: "cell-output",
            cell_id: CELL_ID,
            code: "slow()",
            output: {
              type: "error",
              instructions: ERROR_MESSAGE_INSTRUCTIONS,
              message: "This cell was interrupted and needs to be re-run",
            },
          },
        }),
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
