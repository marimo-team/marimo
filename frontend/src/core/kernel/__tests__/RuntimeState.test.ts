/* Copyright 2024 Marimo. All rights reserved. */

import {
  beforeEach,
  describe,
  expect,
  type MockedFunction,
  test,
  vi,
} from "vitest";
import { MarimoValueReadyEvent } from "@/core/dom/events";
import { UIElementRegistry } from "@/core/dom/uiregistry";
import type { RunRequests } from "@/core/network/types";
import { RuntimeState } from "../RuntimeState";

const addEventListenerSpy = vi.spyOn(document, "addEventListener");
const removeEventListenerSpy = vi.spyOn(document, "removeEventListener");

describe("RuntimeState", () => {
  let runtimeState: RuntimeState;
  let mockSendComponentValues: MockedFunction<
    RunRequests["sendComponentValues"]
  >;
  let uiElementRegistry: UIElementRegistry;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSendComponentValues = vi.fn((args) => Promise.resolve(null));
    uiElementRegistry = UIElementRegistry.INSTANCE;
    uiElementRegistry.entries.clear();

    runtimeState = new RuntimeState(uiElementRegistry);
  });

  test("start should register event listener", () => {
    runtimeState.start(mockSendComponentValues);
    expect(addEventListenerSpy).toHaveBeenCalledWith(
      MarimoValueReadyEvent.TYPE,
      expect.any(Function),
    );
  });

  test("it can only start once", () => {
    runtimeState.start(mockSendComponentValues);
    runtimeState.start(mockSendComponentValues);
    expect(addEventListenerSpy).toHaveBeenCalledTimes(1);
  });

  test("stop should remove event listener", () => {
    runtimeState.start(mockSendComponentValues);
    runtimeState.stop();
    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      MarimoValueReadyEvent.TYPE,
      expect.any(Function),
    );
  });
});
