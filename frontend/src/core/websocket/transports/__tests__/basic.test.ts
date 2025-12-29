/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { BasicTransport } from "../basic";

describe("BasicTransport", () => {
  describe("close", () => {
    it("should trigger close event", () => {
      const transport = BasicTransport.empty();
      const closeCallback = vi.fn();

      transport.addEventListener("close", closeCallback);
      transport.close();

      expect(closeCallback).toHaveBeenCalledTimes(1);
      expect(closeCallback).toHaveBeenCalledWith(expect.any(Event));
    });
  });

  describe("reconnect", () => {
    it("should trigger close and open events", async () => {
      const transport = BasicTransport.empty();
      const openCallback = vi.fn();
      const closeCallback = vi.fn();

      transport.addEventListener("open", openCallback);
      transport.addEventListener("close", closeCallback);

      // Clear the initial open callback
      openCallback.mockClear();

      transport.reconnect();

      // Wait for connect to complete
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(closeCallback).toHaveBeenCalledTimes(1);
      expect(openCallback).toHaveBeenCalledTimes(1);
    });
  });

  describe("send", () => {
    it("should trigger message event with string data", async () => {
      const transport = BasicTransport.empty();
      const messageCallback = vi.fn();

      transport.addEventListener("message", messageCallback);

      transport.send("test message");

      expect(messageCallback).toHaveBeenCalledTimes(1);
      expect(messageCallback).toHaveBeenCalledWith(
        expect.objectContaining({
          data: "test message",
        }),
      );
    });

    it("should trigger message event with ArrayBuffer data", async () => {
      const transport = BasicTransport.empty();
      const messageCallback = vi.fn();

      transport.addEventListener("message", messageCallback);

      const buffer = new ArrayBuffer(8);
      transport.send(buffer);

      expect(messageCallback).toHaveBeenCalledTimes(1);
      expect(messageCallback).toHaveBeenCalledWith(
        expect.objectContaining({
          data: buffer,
        }),
      );
    });
  });

  describe("addEventListener", () => {
    it("should add open event listener and call it immediately", () => {
      const transport = BasicTransport.empty();
      const callback = vi.fn();

      transport.addEventListener("open", callback);

      expect(callback).toHaveBeenCalledTimes(1);
      expect(callback).toHaveBeenCalledWith(expect.any(Event));
    });

    it("should add message event listener and start producer", () => {
      const producer = vi.fn();
      const transport = BasicTransport.withProducerCallback(producer);
      const callback = vi.fn();

      transport.addEventListener("message", callback);

      // Producer should be called once
      expect(producer).toHaveBeenCalledTimes(1);
      expect(producer).toHaveBeenCalledWith(expect.any(Function));
    });
  });

  describe("removeEventListener", () => {
    it("should remove event listener", async () => {
      const transport = BasicTransport.empty();
      const callback = vi.fn();

      transport.addEventListener("message", callback);
      transport.removeEventListener("message", callback);

      transport.send("test");

      expect(callback).not.toHaveBeenCalled();
    });

    it("should only remove the specific listener", () => {
      const transport = BasicTransport.empty();
      const callback1 = vi.fn();
      const callback2 = vi.fn();

      transport.addEventListener("close", callback1);
      transport.addEventListener("close", callback2);

      transport.removeEventListener("close", callback1);

      transport.close();

      expect(callback1).not.toHaveBeenCalled();
      expect(callback2).toHaveBeenCalledTimes(1);
    });
  });

  describe("Producer functionality", () => {
    it("should pass producer callback that triggers message events", () => {
      let producerCallback: ((message: MessageEvent) => void) | undefined;
      const producer = vi.fn((callback) => {
        producerCallback = callback;
      });
      const transport = BasicTransport.withProducerCallback(producer);
      const messageCallback = vi.fn();

      transport.addEventListener("message", messageCallback);

      expect(producerCallback).toBeDefined();

      const testMessage = new MessageEvent("message", { data: "test" });
      producerCallback?.(testMessage);

      expect(messageCallback).toHaveBeenCalledWith(testMessage);
    });

    it("should handle multiple messages from producer", () => {
      let producerCallback: ((message: MessageEvent) => void) | undefined;
      const producer = vi.fn((callback) => {
        producerCallback = callback;
      });
      const transport = BasicTransport.withProducerCallback(producer);
      const messageCallback = vi.fn();

      transport.addEventListener("message", messageCallback);

      producerCallback?.(new MessageEvent("message", { data: "msg1" }));
      producerCallback?.(new MessageEvent("message", { data: "msg2" }));
      producerCallback?.(new MessageEvent("message", { data: "msg3" }));

      expect(messageCallback).toHaveBeenCalledTimes(3);
      expect(messageCallback).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({ data: "msg1" }),
      );
      expect(messageCallback).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({ data: "msg2" }),
      );
      expect(messageCallback).toHaveBeenNthCalledWith(
        3,
        expect.objectContaining({ data: "msg3" }),
      );
    });

    it("should not start producer if no message listener is added", () => {
      const producer = vi.fn();
      const transport = BasicTransport.withProducerCallback(producer);

      transport.addEventListener("open", vi.fn());
      transport.addEventListener("close", vi.fn());

      expect(producer).not.toHaveBeenCalled();
    });
  });

  describe("Integration scenarios", () => {
    it("should handle complete connection lifecycle", async () => {
      const transport = BasicTransport.empty();
      const openCallback = vi.fn();
      const closeCallback = vi.fn();

      transport.addEventListener("open", openCallback);
      transport.addEventListener("close", closeCallback);

      expect(openCallback).toHaveBeenCalledTimes(1);

      transport.reconnect();
      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(openCallback).toHaveBeenCalledTimes(2);
      expect(closeCallback).toHaveBeenCalledTimes(1);

      transport.close();
      expect(closeCallback).toHaveBeenCalledTimes(2);
    });

    it("should handle send and receive flow", async () => {
      let producerCallback: ((message: MessageEvent) => void) | undefined;
      const producer = vi.fn((callback) => {
        producerCallback = callback;
      });
      const transport = BasicTransport.withProducerCallback(producer);
      const messageCallback = vi.fn();

      transport.addEventListener("message", messageCallback);

      transport.send("outgoing");
      expect(messageCallback).toHaveBeenCalledWith(
        expect.objectContaining({ data: "outgoing" }),
      );

      messageCallback.mockClear();

      producerCallback?.(new MessageEvent("message", { data: "incoming" }));
      expect(messageCallback).toHaveBeenCalledWith(
        expect.objectContaining({ data: "incoming" }),
      );
    });

    it("should maintain separate event queues for different event types", async () => {
      const transport = BasicTransport.empty();
      const openCallback = vi.fn();
      const closeCallback = vi.fn();
      const messageCallback = vi.fn();

      transport.addEventListener("open", openCallback);
      transport.addEventListener("close", closeCallback);
      transport.addEventListener("message", messageCallback);

      openCallback.mockClear();

      transport.reconnect();
      await new Promise((resolve) => setTimeout(resolve, 10));
      transport.send("test");
      transport.close();

      expect(openCallback).toHaveBeenCalledTimes(1);
      expect(messageCallback).toHaveBeenCalledTimes(1);
      expect(closeCallback).toHaveBeenCalledTimes(2);
    });

    it("should handle rapid reconnections", async () => {
      const transport = BasicTransport.empty();
      const openCallback = vi.fn();
      const closeCallback = vi.fn();

      transport.addEventListener("open", openCallback);
      transport.addEventListener("close", closeCallback);

      openCallback.mockClear();

      transport.reconnect();
      transport.reconnect();
      transport.reconnect();

      await new Promise((resolve) => setTimeout(resolve, 20));

      expect(closeCallback).toHaveBeenCalledTimes(3);
      expect(openCallback).toHaveBeenCalledTimes(3);
    });
  });
});
