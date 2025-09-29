/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UIElementId } from "@/core/cells/ids";
import {
  MarimoValueInputEvent,
  type MarimoValueInputEventType,
  MarimoValueUpdateEvent,
  type MarimoValueUpdateEventType,
} from "../events";
import { initializeUIElement } from "../ui-element";
import { UIElementRegistry } from "../uiregistry";

// Mock the registerReactComponent module
vi.mock("@/plugins/core/registerReactComponent", () => ({
  isCustomMarimoElement: (element: Element | null) => {
    return element?.tagName === "MOCK-CUSTOM-ELEMENT";
  },
}));

describe("UIElement", () => {
  let registry: UIElementRegistry;

  beforeEach(() => {
    // Clear registry before each test
    registry = UIElementRegistry.INSTANCE;
    registry.entries.clear();

    // Initialize UIElement component
    initializeUIElement();
  });

  it("should preserve value during random-id attribute change (remounting)", () => {
    // Create a mock custom element
    class MockCustomElement extends HTMLElement {
      rerender() {
        // Mock rerender method
      }

      reset() {
        // Mock reset method
      }
    }
    customElements.define("mock-custom-element", MockCustomElement);

    // Create UI element with initial setup
    const uiElement = document.createElement("marimo-ui-element");
    const mockChild = document.createElement("mock-custom-element");

    // Set up the UI element attributes
    const objectId = "AbCd-widget123" as UIElementId;
    uiElement.setAttribute("object-id", objectId);
    uiElement.setAttribute("random-id", "initial-random-id");
    uiElement.append(mockChild);

    // Add to DOM to trigger connectedCallback
    document.body.append(uiElement);

    // Verify initial registration
    expect(registry.has(objectId)).toBe(true);

    // Set a value in the registry to simulate user interaction
    const testValue = "user-entered-value";
    registry.entries.get(objectId)!.value = testValue;

    // Track events dispatched
    const inputEvents: MarimoValueInputEventType[] = [];
    const updateEvents: MarimoValueUpdateEventType[] = [];

    document.addEventListener(MarimoValueInputEvent.TYPE, (e) => {
      inputEvents.push(e);
    });

    document.addEventListener(MarimoValueUpdateEvent.TYPE, (e) => {
      updateEvents.push(e);
    });

    // Simulate random-id change (what happens during cell re-execution)
    uiElement.setAttribute("random-id", "new-random-id");

    // Verify the value is preserved after remounting
    expect(registry.lookupValue(objectId)).toBe(testValue);

    // Verify no input events were dispatched (this prevents infinite loop)
    expect(inputEvents).toHaveLength(0);

    // Verify no update events were dispatched (value restoration doesn't trigger events)
    expect(updateEvents).toHaveLength(0);

    // Cleanup
    uiElement.remove();
  });

  it("should handle remounting when no previous value exists", () => {
    // Create a mock custom element
    class MockCustomElement extends HTMLElement {
      rerender() {
        // Mock rerender method
      }
    }
    customElements.define("mock-custom-element-2", MockCustomElement);

    // Create UI element
    const uiElement = document.createElement("marimo-ui-element");
    const mockChild = document.createElement("mock-custom-element-2");

    const objectId = "EfGh-widget456" as UIElementId;
    uiElement.setAttribute("object-id", objectId);
    uiElement.setAttribute("random-id", "initial-random-id");
    uiElement.append(mockChild);

    // Add to DOM
    document.body.append(uiElement);

    // Verify initial registration
    expect(registry.has(objectId)).toBe(true);

    // Don't set any value (simulates fresh widget)
    const initialValue = registry.lookupValue(objectId);

    // Simulate random-id change
    uiElement.setAttribute("random-id", "new-random-id");

    // Verify the element is still registered and value remains undefined
    expect(registry.has(objectId)).toBe(true);
    expect(registry.lookupValue(objectId)).toBe(initialValue);

    // Cleanup
    uiElement.remove();
  });

  it("should handle multiple UI elements with different values during remounting", () => {
    // Create mock custom elements
    class MockCustomElement extends HTMLElement {
      rerender() {} // eslint-disable-line @typescript-eslint/no-empty-function
    }
    customElements.define("mock-custom-element-3", MockCustomElement);

    // Create two UI elements (simulating grouped widgets)
    const uiElement1 = document.createElement("marimo-ui-element");
    const mockChild1 = document.createElement("mock-custom-element-3");
    const objectId1 = "IjKl-widget1" as UIElementId;
    uiElement1.setAttribute("object-id", objectId1);
    uiElement1.setAttribute("random-id", "random-1");
    uiElement1.append(mockChild1);

    const uiElement2 = document.createElement("marimo-ui-element");
    const mockChild2 = document.createElement("mock-custom-element-3");
    const objectId2 = "MnOp-widget2" as UIElementId;
    uiElement2.setAttribute("object-id", objectId2);
    uiElement2.setAttribute("random-id", "random-2");
    uiElement2.append(mockChild2);

    // Add to DOM
    document.body.append(uiElement1);
    document.body.append(uiElement2);

    // Set different values for each widget
    const value1 = "search-term";
    const value2 = "dropdown-selection";

    registry.entries.get(objectId1)!.value = value1;
    registry.entries.get(objectId2)!.value = value2;

    // Simulate remounting both elements (happens when cell re-executes)
    uiElement1.setAttribute("random-id", "new-random-1");
    uiElement2.setAttribute("random-id", "new-random-2");

    // Verify both values are preserved
    expect(registry.lookupValue(objectId1)).toBe(value1);
    expect(registry.lookupValue(objectId2)).toBe(value2);

    // Cleanup
    uiElement1.remove();
    uiElement2.remove();
  });

  it("should not interfere with normal attribute changes", () => {
    // Create mock custom element
    class MockCustomElement extends HTMLElement {
      rerender() {} // eslint-disable-line @typescript-eslint/no-empty-function
    }
    customElements.define("mock-custom-element-4", MockCustomElement);

    const uiElement = document.createElement("marimo-ui-element");
    const mockChild = document.createElement("mock-custom-element-4");

    const objectId = "QrSt-widget789" as UIElementId;
    uiElement.setAttribute("object-id", objectId);
    uiElement.setAttribute("random-id", "random-id");
    uiElement.append(mockChild);

    document.body.append(uiElement);

    const testValue = "test-value";
    registry.entries.get(objectId)!.value = testValue;

    // Change a different attribute (not random-id)
    uiElement.setAttribute("some-other-attr", "new-value");

    // Value should remain unchanged
    expect(registry.lookupValue(objectId)).toBe(testValue);

    // Cleanup
    uiElement.remove();
  });

  it("should debounce input events when data-debounce attribute is set", () => {
    vi.useFakeTimers();

    // Create mock custom element
    class MockCustomElement extends HTMLElement {
      rerender() {} // eslint-disable-line @typescript-eslint/no-empty-function
    }
    customElements.define("mock-custom-element-debounce", MockCustomElement);

    const uiElement = document.createElement("marimo-ui-element");
    const mockChild = document.createElement("mock-custom-element-debounce");

    // Set debounce delay on child element
    mockChild.dataset.debounce = "300";

    const objectId = "UvWx-debounce123" as UIElementId;
    uiElement.setAttribute("object-id", objectId);
    uiElement.append(mockChild);

    document.body.append(uiElement);

    // Spy on broadcastValueUpdate to verify debouncing
    const broadcastSpy = vi.spyOn(registry, "broadcastValueUpdate");

    // Simulate rapid input events
    const event1 = new CustomEvent("marimo-value-input", {
      detail: { element: mockChild, value: "a" },
    });
    const event2 = new CustomEvent("marimo-value-input", {
      detail: { element: mockChild, value: "ab" },
    });
    const event3 = new CustomEvent("marimo-value-input", {
      detail: { element: mockChild, value: "abc" },
    });

    // Dispatch events rapidly
    document.dispatchEvent(event1);
    document.dispatchEvent(event2);
    document.dispatchEvent(event3);

    // Should not have called broadcast immediately
    expect(broadcastSpy).not.toHaveBeenCalled();

    // Fast-forward to just before the delay
    vi.advanceTimersByTime(299);
    expect(broadcastSpy).not.toHaveBeenCalled();

    // Fast-forward past the delay
    vi.advanceTimersByTime(1);

    // Should have called broadcast only once with the final value
    expect(broadcastSpy).toHaveBeenCalledTimes(1);
    expect(broadcastSpy).toHaveBeenCalledWith(mockChild, objectId, "abc");

    // Cleanup
    vi.useRealTimers();
    uiElement.remove();
    broadcastSpy.mockRestore();
  });

  it("should immediately broadcast when no debounce is set", () => {
    // Create mock custom element
    class MockCustomElement extends HTMLElement {
      rerender() {} // eslint-disable-line @typescript-eslint/no-empty-function
    }
    customElements.define("mock-custom-element-immediate", MockCustomElement);

    const uiElement = document.createElement("marimo-ui-element");
    const mockChild = document.createElement("mock-custom-element-immediate");

    const objectId = "YzAb-immediate123" as UIElementId;
    uiElement.setAttribute("object-id", objectId);
    uiElement.append(mockChild);

    document.body.append(uiElement);

    // Spy on broadcastValueUpdate
    const broadcastSpy = vi.spyOn(registry, "broadcastValueUpdate");

    // Simulate input event
    const event = new CustomEvent("marimo-value-input", {
      detail: { element: mockChild, value: "immediate" },
    });

    document.dispatchEvent(event);

    // Should have called broadcast immediately
    expect(broadcastSpy).toHaveBeenCalledTimes(1);
    expect(broadcastSpy).toHaveBeenCalledWith(mockChild, objectId, "immediate");

    // Cleanup
    uiElement.remove();
    broadcastSpy.mockRestore();
  });

  it("should prevent input events during attribute change processing", () => {
    // Create mock custom element
    class MockCustomElement extends HTMLElement {
      rerender() {} // eslint-disable-line @typescript-eslint/no-empty-function
    }
    customElements.define("mock-custom-element-processing", MockCustomElement);

    const uiElement = document.createElement("marimo-ui-element");
    const mockChild = document.createElement("mock-custom-element-processing");

    const objectId = "CdEf-processing123" as UIElementId;
    uiElement.setAttribute("object-id", objectId);
    uiElement.setAttribute("random-id", "initial");
    uiElement.append(mockChild);

    document.body.append(uiElement);

    // Spy on broadcastValueUpdate
    const broadcastSpy = vi.spyOn(registry, "broadcastValueUpdate");

    // Start attribute change (simulates remounting)
    uiElement.setAttribute("random-id", "new-id");

    // Try to dispatch input event during processing
    const event = new CustomEvent("marimo-value-input", {
      detail: { element: mockChild, value: "should-be-ignored" },
    });

    document.dispatchEvent(event);

    // Should not have called broadcast during processing
    expect(broadcastSpy).not.toHaveBeenCalled();

    // Cleanup
    uiElement.remove();
    broadcastSpy.mockRestore();
  });
});
