/* Copyright 2024 Marimo. All rights reserved. */
import { marimoValueReadyEvent } from "@/core/dom/events";
import { UIElementRegistry } from "@/core/dom/uiregistry";
import { describe, beforeEach, expect, vi, test, MockedFunction } from "vitest";
import { RuntimeState } from "../RuntimeState";
import { RunRequests } from "@/core/network/types";

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
      marimoValueReadyEvent,
      expect.any(Function),
    );
  });

  test("stop should remove event listener", () => {
    runtimeState.stop();
    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      marimoValueReadyEvent,
      expect.any(Function),
    );
  });
});
