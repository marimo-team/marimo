/* Copyright 2024 Marimo. All rights reserved. */
import { marimoValueReadyEvent } from "@/core/dom/events";
import { UIElementRegistry } from "@/core/dom/uiregistry";
import { describe, beforeEach, expect, vi, test, MockedFunction } from "vitest";
import { RuntimeState } from "../RuntimeState";
import { RunRequests } from "@/core/network/types";
import { UIElementId } from "@/core/cells/ids";

const elementOne = document.createElement("div");
const uiElementOneId = "uiElementOne" as UIElementId;
const elementTwo = document.createElement("div");
const uiElementTwoId = "uiElementTwo" as UIElementId;

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

    runtimeState = new RuntimeState(uiElementRegistry, {
      sendComponentValues: mockSendComponentValues,
    });
  });

  test("start should register event listener", () => {
    runtimeState.start();
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

  test("registerRunStart should increment runningCount", () => {
    runtimeState.registerRunStart();
    expect(runtimeState.running()).toBe(true);
  });

  test("registerRunEnd should decrement runningCount", () => {
    runtimeState.registerRunStart();
    runtimeState.registerRunStart();
    runtimeState.registerRunEnd();
    expect(runtimeState.running()).toBe(true); // still running
    runtimeState.registerRunEnd();
    expect(runtimeState.running()).toBe(false); // not running
  });

  test("flushUpdates should not call sendComponentValues if no updates", () => {
    runtimeState.flushUpdates();
    expect(mockSendComponentValues).not.toHaveBeenCalled();
  });

  test("flushUpdates should call sendComponentValues with updates", async () => {
    runtimeState.start();
    uiElementRegistry.registerInstance(uiElementOneId, elementOne);
    expect(uiElementRegistry.entries).toHaveLength(1);
    expect(mockSendComponentValues).not.toHaveBeenCalled();

    uiElementRegistry.broadcastValueUpdate(elementOne, uiElementOneId, "10");
    expect(mockSendComponentValues).toHaveBeenCalledOnce();
    expect(mockSendComponentValues.mock.lastCall?.[0]).toMatchInlineSnapshot(`
      [
        {
          "objectId": "uiElementOne",
          "value": "10",
        },
      ]
    `);
    expect(runtimeState.running()).toBe(true);
  });

  test("will only send one broadcast at a time and hold future events", () => {
    runtimeState.start();
    uiElementRegistry.registerInstance(uiElementOneId, elementOne);
    uiElementRegistry.registerInstance(uiElementTwoId, elementTwo);
    uiElementRegistry.broadcastValueUpdate(elementOne, uiElementOneId, "10");
    // Set while running
    uiElementRegistry.broadcastValueUpdate(elementTwo, uiElementTwoId, "20");
    uiElementRegistry.broadcastValueUpdate(elementOne, uiElementOneId, "30");
    expect(mockSendComponentValues).toHaveBeenCalledOnce();
    expect(mockSendComponentValues.mock.lastCall?.[0]).toMatchInlineSnapshot(`
      [
        {
          "objectId": "uiElementOne",
          "value": "10",
        },
      ]
    `);
    expect(runtimeState.running()).toBe(true);

    // End run
    runtimeState.registerRunEnd();
    expect(runtimeState.running()).toBe(false);

    // Start another run, this overwrites the previous value that was not sent
    uiElementRegistry.broadcastValueUpdate(elementTwo, uiElementTwoId, "40");
    expect(mockSendComponentValues).toHaveBeenCalledTimes(2);
    // We expect 2 values to be sent, the last value of uiElementTwo and the last value of uiElementOne
    // both that were set while running
    expect(mockSendComponentValues.mock.lastCall?.[0]).toMatchInlineSnapshot(`
      [
        {
          "objectId": "uiElementTwo",
          "value": "40",
        },
        {
          "objectId": "uiElementOne",
          "value": "30",
        },
      ]
    `);
    expect(runtimeState.running()).toBe(true);
  });

  test("handle when sendComponentValues fails", async () => {
    runtimeState.start();
    uiElementRegistry.registerInstance(uiElementOneId, elementOne);
    uiElementRegistry.registerInstance(uiElementTwoId, elementTwo);
    expect(uiElementRegistry.entries).toHaveLength(2);
    expect(mockSendComponentValues).not.toHaveBeenCalled();

    const error = new Error("Failed to send component values");
    mockSendComponentValues.mockRejectedValueOnce(error);

    uiElementRegistry.broadcastValueUpdate(elementOne, uiElementOneId, "10");
    // flush the event loop
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(mockSendComponentValues).toHaveBeenCalledOnce();
    expect(mockSendComponentValues.mock.lastCall?.[0]).toMatchInlineSnapshot(`
      [
        {
          "objectId": "uiElementOne",
          "value": "10",
        },
      ]
    `);

    // It should not be running anymore
    expect(runtimeState.running()).toBe(false);

    // And if we try another element, we should send both (since the previous one failed)
    uiElementRegistry.broadcastValueUpdate(elementTwo, uiElementTwoId, "20");
    expect(mockSendComponentValues).toHaveBeenCalledTimes(2);
    expect(mockSendComponentValues.mock.lastCall?.[0]).toMatchInlineSnapshot(`
      [
        {
          "objectId": "uiElementOne",
          "value": "10",
        },
        {
          "objectId": "uiElementTwo",
          "value": "20",
        },
      ]
    `);
  });
});
