/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { document as documentOf } from "@/core/notebook/document/__tests__/fixtures";
import {
  type FakeInput,
  fakeBackend,
} from "@/core/notebook/replica/__tests__/fixtures";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import { replyInput } from "../input";

const toast = vi.fn();
vi.mock("@/components/ui/use-toast", () => ({
  toast: (...args: unknown[]) => toast(...args),
}));

describe("replyInput", () => {
  let input: ReturnType<typeof vi.fn<FakeInput>>;

  beforeEach(() => {
    toast.mockClear();
    input = vi.fn<FakeInput>(async (_notebookId, inputId) => ({
      ok: true,
      status: 200,
      data: {
        id: inputId,
        execution_id: "e1",
        seq: 0,
        prompt: "Name: ",
        password: false,
        status: "answered",
      },
    }));
    const replica = MockExecutions.seed(
      store,
      [],
      MockExecutions.runtime("running"),
      documentOf(),
    );
    store.set(replica.backendAtom, fakeBackend({ input }));
  });

  afterEach(() => {
    store.set(activeNotebookReplicaAtom, null);
  });

  it("answers the prompt by id in the connected notebook", async () => {
    await replyInput(store, "prompt-1", "marimo");

    expect(input).toHaveBeenCalledWith("n1", "prompt-1", { value: "marimo" });
    expect(toast).not.toHaveBeenCalled();
  });

  it("reports a reply the host refuses", async () => {
    input.mockResolvedValue({
      ok: false,
      status: 409,
      problem: {
        type: "tag:marimo.io,2026:host/conflict",
        title: "Conflict",
        status: 409,
        detail: "input prompt-1 has already ended.",
      },
    });

    await replyInput(store, "prompt-1", "marimo");

    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Failed to send input",
        description: "input prompt-1 has already ended.",
      }),
    );
  });

  it("does nothing without a connected notebook", async () => {
    store.set(activeNotebookReplicaAtom, null);

    await replyInput(store, "prompt-1", "marimo");

    expect(input).not.toHaveBeenCalled();
    expect(toast).not.toHaveBeenCalled();
  });
});
