/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { ConnectionSubscriptions } from "../transport";

describe("ConnectionSubscriptions", () => {
  describe("addSubscription", () => {
    it("should add a subscription for an event", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback = vi.fn();

      subscriptions.addSubscription("open", callback);

      // Verify by notifying
      subscriptions.notify("open", new Event("open"));
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it("should add multiple subscriptions for the same event", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback1 = vi.fn();
      const callback2 = vi.fn();
      const callback3 = vi.fn();

      subscriptions.addSubscription("message", callback1);
      subscriptions.addSubscription("message", callback2);
      subscriptions.addSubscription("message", callback3);

      const messageEvent = new MessageEvent("message", { data: "test" });
      subscriptions.notify("message", messageEvent);

      expect(callback1).toHaveBeenCalledWith(messageEvent);
      expect(callback2).toHaveBeenCalledWith(messageEvent);
      expect(callback3).toHaveBeenCalledWith(messageEvent);
    });

    it("should add subscriptions for different event types", () => {
      const subscriptions = new ConnectionSubscriptions();
      const openCallback = vi.fn();
      const closeCallback = vi.fn();
      const messageCallback = vi.fn();

      subscriptions.addSubscription("open", openCallback);
      subscriptions.addSubscription("close", closeCallback);
      subscriptions.addSubscription("message", messageCallback);

      subscriptions.notify("open", new Event("open"));
      expect(openCallback).toHaveBeenCalledTimes(1);
      expect(closeCallback).not.toHaveBeenCalled();
      expect(messageCallback).not.toHaveBeenCalled();
    });

    it("should not add duplicate subscriptions for the same callback", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback = vi.fn();

      subscriptions.addSubscription("close", callback);
      subscriptions.addSubscription("close", callback);
      subscriptions.addSubscription("close", callback);

      subscriptions.notify("close", new Event("close"));

      // Set only stores unique callbacks, so should be called once
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe("removeSubscription", () => {
    it("should remove a subscription", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback = vi.fn();

      subscriptions.addSubscription("message", callback);
      subscriptions.removeSubscription("message", callback);

      const messageEvent = new MessageEvent("message", { data: "test" });
      subscriptions.notify("message", messageEvent);

      expect(callback).not.toHaveBeenCalled();
    });

    it("should only remove the specific callback", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback1 = vi.fn();
      const callback2 = vi.fn();
      const callback3 = vi.fn();

      subscriptions.addSubscription("close", callback1);
      subscriptions.addSubscription("close", callback2);
      subscriptions.addSubscription("close", callback3);

      subscriptions.removeSubscription("close", callback2);

      subscriptions.notify("close", new Event("close"));

      expect(callback1).toHaveBeenCalledTimes(1);
      expect(callback2).not.toHaveBeenCalled();
      expect(callback3).toHaveBeenCalledTimes(1);
    });

    it("should handle removing subscription from non-existent event type", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback = vi.fn();

      subscriptions.addSubscription("open", callback);

      expect(() =>
        subscriptions.removeSubscription("close", callback),
      ).not.toThrow();

      subscriptions.notify("open", new Event("open"));
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe("notify", () => {
    it("should notify all subscribed callbacks for an event", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback1 = vi.fn();
      const callback2 = vi.fn();

      subscriptions.addSubscription("open", callback1);
      subscriptions.addSubscription("open", callback2);

      const openEvent = new Event("open");
      subscriptions.notify("open", openEvent);

      expect(callback1).toHaveBeenCalledWith(openEvent);
      expect(callback2).toHaveBeenCalledWith(openEvent);
    });

    it("should pass the correct data to callbacks", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback = vi.fn();

      subscriptions.addSubscription("message", callback);

      const messageEvent = new MessageEvent("message", {
        data: "test data",
      });
      subscriptions.notify("message", messageEvent);

      expect(callback).toHaveBeenCalledWith(messageEvent);
      expect(callback.mock.calls[0][0].data).toBe("test data");
    });

    it("should not notify callbacks for different event types", () => {
      const subscriptions = new ConnectionSubscriptions();
      const openCallback = vi.fn();
      const closeCallback = vi.fn();

      subscriptions.addSubscription("open", openCallback);
      subscriptions.addSubscription("close", closeCallback);

      subscriptions.notify("open", new Event("open"));

      expect(openCallback).toHaveBeenCalledTimes(1);
      expect(closeCallback).not.toHaveBeenCalled();
    });

    it("should handle exceptions in callbacks without affecting other callbacks", () => {
      const subscriptions = new ConnectionSubscriptions();
      const throwingCallback = vi.fn(() => {
        throw new Error("Callback error");
      });
      const normalCallback = vi.fn();

      subscriptions.addSubscription("message", throwingCallback);
      subscriptions.addSubscription("message", normalCallback);

      const messageEvent = new MessageEvent("message", { data: "test" });

      expect(() => subscriptions.notify("message", messageEvent)).toThrow(
        "Callback error",
      );

      expect(throwingCallback).toHaveBeenCalledWith(messageEvent);
      expect(normalCallback).not.toHaveBeenCalled();
    });
  });

  describe("Integration scenarios", () => {
    it("should handle complete subscription lifecycle", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback = vi.fn();

      subscriptions.addSubscription("open", callback);

      subscriptions.notify("open", new Event("open"));
      expect(callback).toHaveBeenCalledTimes(1);

      subscriptions.removeSubscription("open", callback);

      subscriptions.notify("open", new Event("open"));
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it("should handle multiple events with multiple callbacks", () => {
      const subscriptions = new ConnectionSubscriptions();

      const openCallback1 = vi.fn();
      const openCallback2 = vi.fn();
      const closeCallback1 = vi.fn();
      const messageCallback = vi.fn();

      subscriptions.addSubscription("open", openCallback1);
      subscriptions.addSubscription("open", openCallback2);
      subscriptions.addSubscription("close", closeCallback1);
      subscriptions.addSubscription("message", messageCallback);

      subscriptions.notify("open", new Event("open"));
      expect(openCallback1).toHaveBeenCalledTimes(1);
      expect(openCallback2).toHaveBeenCalledTimes(1);
      expect(closeCallback1).not.toHaveBeenCalled();
      expect(messageCallback).not.toHaveBeenCalled();

      const messageEvent = new MessageEvent("message", { data: "test" });
      subscriptions.notify("message", messageEvent);
      expect(openCallback1).toHaveBeenCalledTimes(1);
      expect(openCallback2).toHaveBeenCalledTimes(1);
      expect(closeCallback1).not.toHaveBeenCalled();
      expect(messageCallback).toHaveBeenCalledTimes(1);
      expect(messageCallback).toHaveBeenCalledWith(messageEvent);

      subscriptions.notify("close", new Event("close"));
      expect(openCallback1).toHaveBeenCalledTimes(1);
      expect(openCallback2).toHaveBeenCalledTimes(1);
      expect(closeCallback1).toHaveBeenCalledTimes(1);
      expect(messageCallback).toHaveBeenCalledTimes(1);
    });

    it("should handle add and remove operations interleaved", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback1 = vi.fn();
      const callback2 = vi.fn();
      const callback3 = vi.fn();

      subscriptions.addSubscription("message", callback1);
      subscriptions.addSubscription("message", callback2);

      const msg1 = new MessageEvent("message", { data: "msg1" });
      subscriptions.notify("message", msg1);

      expect(callback1).toHaveBeenCalledWith(msg1);
      expect(callback2).toHaveBeenCalledWith(msg1);
      expect(callback3).not.toHaveBeenCalled();

      subscriptions.removeSubscription("message", callback1);
      subscriptions.addSubscription("message", callback3);

      const msg2 = new MessageEvent("message", { data: "msg2" });
      subscriptions.notify("message", msg2);

      expect(callback1).toHaveBeenCalledTimes(1);
      expect(callback2).toHaveBeenCalledWith(msg2);
      expect(callback3).toHaveBeenCalledWith(msg2);
    });

    it("should maintain separate subscription lists per event type", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback = vi.fn();

      subscriptions.addSubscription("open", callback);
      subscriptions.addSubscription("close", callback);
      subscriptions.addSubscription("message", callback);

      subscriptions.removeSubscription("close", callback);

      subscriptions.notify("open", new Event("open"));
      expect(callback).toHaveBeenCalledTimes(1);

      subscriptions.notify(
        "message",
        new MessageEvent("message", { data: "test" }),
      );
      expect(callback).toHaveBeenCalledTimes(2);

      subscriptions.notify("close", new Event("close"));
      expect(callback).toHaveBeenCalledTimes(2);
    });
  });

  describe("Edge cases", () => {
    it("should handle callback that modifies subscriptions", () => {
      const subscriptions = new ConnectionSubscriptions();
      const callback1 = vi.fn();
      const callback2 = vi.fn(() => {
        subscriptions.removeSubscription("message", callback1);
      });

      subscriptions.addSubscription("message", callback1);
      subscriptions.addSubscription("message", callback2);

      const messageEvent = new MessageEvent("message", { data: "test" });
      subscriptions.notify("message", messageEvent);

      expect(callback1).toHaveBeenCalledTimes(1);
      expect(callback2).toHaveBeenCalledTimes(1);

      callback1.mockClear();
      callback2.mockClear();

      subscriptions.notify("message", messageEvent);
      expect(callback1).not.toHaveBeenCalled();
      expect(callback2).toHaveBeenCalledTimes(1);
    });
  });
});
