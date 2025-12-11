/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { IframeCapabilities } from "../capabilities";

describe("capabilities", () => {
  let Logger: { log: Mock; warn: Mock };
  let getIframeCapabilities: () => IframeCapabilities;

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.unstubAllGlobals();

    // Mock Logger before importing capabilities
    vi.doMock("../Logger", () => ({
      Logger: {
        log: vi.fn(),
        warn: vi.fn(),
      },
    }));

    // Re-import the modules after mocking
    const loggerModule = await import("../Logger");
    Logger = loggerModule.Logger as unknown as { log: Mock; warn: Mock };

    const capabilitiesModule = await import("../capabilities");
    getIframeCapabilities = capabilitiesModule.getIframeCapabilities;
  });

  describe("testStorage", () => {
    it("should detect available localStorage", async () => {
      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(),
        getItem: vi.fn((key) => (key === "__storage_test__" ? "test" : null)),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("localStorage", mockStorage);

      const capabilities = getIframeCapabilities();

      expect(capabilities.hasLocalStorage).toBe(true);
      expect(mockStorage.setItem).toHaveBeenCalledWith(
        "__storage_test__",
        "test",
      );
      expect(mockStorage.getItem).toHaveBeenCalledWith("__storage_test__");
      expect(mockStorage.removeItem).toHaveBeenCalledWith("__storage_test__");
    });

    it("should detect unavailable localStorage when getItem returns wrong value", async () => {
      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(),
        getItem: vi.fn(() => "wrong-value"),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("localStorage", mockStorage);

      const capabilities = getIframeCapabilities();

      expect(capabilities.hasLocalStorage).toBe(false);
    });

    it("should detect available sessionStorage", async () => {
      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(),
        getItem: vi.fn((key) => (key === "__storage_test__" ? "test" : null)),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("sessionStorage", mockStorage);

      const capabilities = getIframeCapabilities();

      expect(capabilities.hasSessionStorage).toBe(true);
    });
  });

  describe("testDownloadCapability", () => {
    it("should detect download capability when anchor supports download attribute", async () => {
      const mockAnchor = {
        download: "",
      };

      const mockDocument = {
        ...document,
        createElement: vi.fn(() => mockAnchor as unknown as HTMLElement),
        fullscreenEnabled: true,
      };

      vi.stubGlobal("document", mockDocument);

      const capabilities = getIframeCapabilities();

      expect(capabilities.hasDownloads).toBe(true);
      expect(mockDocument.createElement).toHaveBeenCalledWith("a");
    });

    it("should detect no download capability when anchor doesn't support download", async () => {
      const mockAnchor = {};

      const mockDocument = {
        ...document,
        createElement: vi.fn(() => mockAnchor as unknown as HTMLElement),
        fullscreenEnabled: false,
      };

      vi.stubGlobal("document", mockDocument);

      const capabilities = getIframeCapabilities();

      expect(capabilities.hasDownloads).toBe(false);
    });
  });

  describe("detectIframeCapabilities", () => {
    it("should detect not embedded when window.parent === window", async () => {
      // In test environment, window.parent === window by default
      const capabilities = getIframeCapabilities();

      expect(capabilities.isEmbedded).toBe(false);
      expect(Logger.log).not.toHaveBeenCalled();
    });

    it("should detect embedded when window.parent !== window", async () => {
      const mockWindow = {
        ...window,
        parent: {} as Window,
      };

      vi.stubGlobal("window", mockWindow);

      const capabilities = getIframeCapabilities();

      expect(capabilities.isEmbedded).toBe(true);
      expect(Logger.log).toHaveBeenCalledWith(
        "[iframe] Running in embedded context",
      );
    });

    it("should detect clipboard availability", async () => {
      vi.stubGlobal("navigator", {
        ...navigator,
        clipboard: {},
      });

      const capabilities = getIframeCapabilities();
      expect(capabilities.hasClipboard).toBe(true);
    });

    it("should detect no clipboard when undefined", async () => {
      vi.stubGlobal("navigator", {
        ...navigator,
        clipboard: undefined,
      });

      const capabilities = getIframeCapabilities();
      expect(capabilities.hasClipboard).toBe(false);
    });

    it("should detect fullscreen availability", async () => {
      vi.stubGlobal("document", {
        ...document,
        fullscreenEnabled: true,
        createElement: vi.fn(
          () => ({ download: "" }) as unknown as HTMLElement,
        ),
      });

      const capabilities = getIframeCapabilities();
      expect(capabilities.hasFullscreen).toBe(true);
    });

    it("should detect no fullscreen when disabled", async () => {
      vi.stubGlobal("document", {
        ...document,
        fullscreenEnabled: false,
        createElement: vi.fn(
          () => ({ download: "" }) as unknown as HTMLElement,
        ),
      });

      const capabilities = getIframeCapabilities();
      expect(capabilities.hasFullscreen).toBe(false);
    });

    it("should detect media devices availability", async () => {
      vi.stubGlobal("navigator", {
        ...navigator,
        mediaDevices: { getUserMedia: vi.fn() },
      });

      const capabilities = getIframeCapabilities();
      expect(capabilities.hasMediaDevices).toBe(true);
    });

    it("should detect no media devices when undefined", async () => {
      vi.stubGlobal("navigator", {
        ...navigator,
        mediaDevices: undefined,
      });

      const capabilities = getIframeCapabilities();
      expect(capabilities.hasMediaDevices).toBe(false);
    });

    it("should detect no media devices when getUserMedia is not a function", async () => {
      vi.stubGlobal("navigator", {
        ...navigator,
        mediaDevices: {},
      });

      const capabilities = getIframeCapabilities();
      expect(capabilities.hasMediaDevices).toBe(false);
    });

    it("should log warnings for missing capabilities when embedded", async () => {
      const mockWindow = {
        ...window,
        parent: {} as Window,
      };

      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(() => {
          throw new Error("blocked");
        }),
        getItem: vi.fn(),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("window", mockWindow);
      vi.stubGlobal("localStorage", mockStorage);
      vi.stubGlobal("sessionStorage", mockStorage);
      vi.stubGlobal("navigator", {
        ...navigator,
        clipboard: undefined,
        mediaDevices: undefined,
      });
      vi.stubGlobal("document", {
        ...document,
        fullscreenEnabled: false,
        createElement: vi.fn(() => {
          throw new Error("blocked");
        }),
      });

      const capabilities = getIframeCapabilities();

      expect(capabilities.isEmbedded).toBe(true);
      expect(Logger.warn).toHaveBeenCalledWith(
        "[iframe] localStorage unavailable - using fallback storage",
      );
      expect(Logger.warn).toHaveBeenCalledWith(
        "[iframe] Clipboard API unavailable",
      );
      expect(Logger.warn).toHaveBeenCalledWith(
        "[iframe] Download capability may be restricted",
      );
      expect(Logger.warn).toHaveBeenCalledWith(
        "[iframe] Fullscreen API unavailable",
      );
      expect(Logger.warn).toHaveBeenCalledWith(
        "[iframe] Media devices API unavailable",
      );
    });

    it("should not log warnings when not embedded even if capabilities missing", async () => {
      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(() => {
          throw new Error("blocked");
        }),
        getItem: vi.fn(),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("localStorage", mockStorage);
      vi.stubGlobal("navigator", {
        ...navigator,
        clipboard: undefined,
      });

      const capabilities = getIframeCapabilities();

      expect(capabilities.isEmbedded).toBe(false);
      expect(Logger.warn).not.toHaveBeenCalled();
    });

    it("should return all capabilities as expected structure", async () => {
      const capabilities = getIframeCapabilities();

      expect(capabilities).toMatchObject({
        isEmbedded: expect.any(Boolean),
        hasLocalStorage: expect.any(Boolean),
        hasSessionStorage: expect.any(Boolean),
        hasClipboard: expect.any(Boolean),
        hasDownloads: expect.any(Boolean),
        hasFullscreen: expect.any(Boolean),
        hasMediaDevices: expect.any(Boolean),
      });
    });
  });

  describe("getIframeCapabilities caching", () => {
    it("should cache capabilities after first call", async () => {
      const mockDocument = {
        ...document,
        createElement: vi.fn(
          () => ({ download: "" }) as unknown as HTMLElement,
        ),
        fullscreenEnabled: true,
      };

      vi.stubGlobal("document", mockDocument);

      const capabilities1 = getIframeCapabilities();
      const capabilities2 = getIframeCapabilities();

      expect(capabilities1).toBe(capabilities2);
      // Should only call detection functions once due to once wrapper
      expect(mockDocument.createElement).toHaveBeenCalledTimes(1);
    });
  });

  describe("complete capability detection scenarios", () => {
    it("should handle fully sandboxed iframe", async () => {
      const mockWindow = {
        ...window,
        parent: {} as Window,
      };

      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(() => {
          throw new Error("blocked");
        }),
        getItem: vi.fn(),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("window", mockWindow);
      vi.stubGlobal("localStorage", mockStorage);
      vi.stubGlobal("sessionStorage", mockStorage);
      vi.stubGlobal("navigator", {
        ...navigator,
        clipboard: undefined,
        mediaDevices: undefined,
      });
      vi.stubGlobal("document", {
        ...document,
        fullscreenEnabled: false,
        createElement: vi.fn(() => {
          throw new Error("blocked");
        }),
      });

      const capabilities = getIframeCapabilities();

      expect(capabilities).toMatchObject({
        isEmbedded: true,
        hasLocalStorage: false,
        hasSessionStorage: false,
        hasClipboard: false,
        hasDownloads: false,
        hasFullscreen: false,
        hasMediaDevices: false,
      });
    });

    it("should handle fully capable standalone context", async () => {
      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(),
        getItem: vi.fn((key) => (key === "__storage_test__" ? "test" : null)),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("localStorage", mockStorage);
      vi.stubGlobal("sessionStorage", mockStorage);
      vi.stubGlobal("navigator", {
        ...navigator,
        clipboard: {},
        mediaDevices: { getUserMedia: vi.fn() },
      });
      vi.stubGlobal("document", {
        ...document,
        fullscreenEnabled: true,
        createElement: vi.fn(
          () => ({ download: "" }) as unknown as HTMLElement,
        ),
      });

      const capabilities = getIframeCapabilities();

      expect(capabilities).toMatchObject({
        isEmbedded: false,
        hasLocalStorage: true,
        hasSessionStorage: true,
        hasClipboard: true,
        hasDownloads: true,
        hasFullscreen: true,
        hasMediaDevices: true,
      });
    });
  });

  describe("edge cases", () => {
    it("should handle localStorage that returns null on getItem", async () => {
      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(),
        getItem: vi.fn(() => null),
        removeItem: vi.fn(),
      };

      vi.stubGlobal("localStorage", mockStorage);

      const capabilities = getIframeCapabilities();

      expect(capabilities.hasLocalStorage).toBe(false);
    });

    it("should handle document.createElement returning null", async () => {
      const mockDocument = {
        ...document,
        createElement: vi.fn(() => null as unknown as HTMLElement),
        fullscreenEnabled: false,
      };

      vi.stubGlobal("document", mockDocument);

      const capabilities = getIframeCapabilities();

      // Should handle gracefully
      expect(capabilities.hasDownloads).toBe(false);
    });

    it("should handle storage.removeItem throwing", async () => {
      const mockStorage: Partial<Storage> = {
        setItem: vi.fn(),
        getItem: vi.fn((key) => (key === "__storage_test__" ? "test" : null)),
        removeItem: vi.fn(() => {
          throw new Error("Cannot remove");
        }),
      };

      vi.stubGlobal("localStorage", mockStorage);

      // Should not throw, should handle error gracefully
      const capabilities = getIframeCapabilities();

      expect(capabilities.hasLocalStorage).toBe(false);
    });
  });
});
