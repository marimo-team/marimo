/* Copyright 2024 Marimo. All rights reserved. */
/** biome-ignore-all lint/suspicious/noConsole: for debugging */
import { type Mock, vi } from "vitest";
import { invariant } from "@/utils/invariant";

// Common mock factories
export const Mocks = {
  quietLogger: () => ({
    debug: vi.fn(),
    log: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    trace: vi.fn(),
    get: vi.fn().mockImplementation(() => Mocks.quietLogger()),
    disabled: vi.fn(),
  }),

  logger: () => ({
    debug: vi.fn().mockImplementation(console.debug),
    log: vi.fn().mockImplementation(console.log),
    warn: vi.fn().mockImplementation(console.warn),
    error: vi.fn().mockImplementation(console.error),
    trace: vi.fn().mockImplementation(console.trace),
    get: vi.fn().mockImplementation(() => Mocks.logger()),
    disabled: vi.fn(),
  }),

  toast: vi.fn(),

  clipboard: () => ({
    write: vi.fn(),
    writeText: vi.fn(),
    read: vi.fn(),
    readText: vi.fn(),
  }),

  clipboardItem: (data: Record<string, string>) => ({
    types: Object.keys(data),
    getType: vi
      .fn()
      .mockImplementation((type: string) =>
        Promise.resolve(new Blob([data[type]?.toString() || ""], { type })),
      ),
    supports: vi.fn().mockReturnValue(true),
  }),

  blob: (parts?: string[], options?: { type?: string }) => ({
    text: () => Promise.resolve(parts?.[0] || ""),
    type: options?.type || "text/plain",
  }),

  event: <T extends React.SyntheticEvent>(props: Partial<T> = {}) => ({
    preventDefault: vi.fn(),
    continuePropagation: vi.fn(),
    target: document.createElement("div"),
    currentTarget: document.createElement("div"),
    stopPropagation: vi.fn(),
    ...props,
  }),

  keyboardEvent: (
    props: Partial<React.KeyboardEvent> = {},
  ): React.KeyboardEvent<HTMLElement> & {
    continuePropagation: () => void;
  } =>
    Mocks.event({
      ...props,
    }) as unknown as React.KeyboardEvent<HTMLElement> & {
      continuePropagation: () => void;
    },
};

// Global mock setup functions
export const SetupMocks = {
  clipboard: (mockClipboard = Mocks.clipboard()) => {
    Object.defineProperty(navigator, "clipboard", {
      value: mockClipboard,
      writable: true,
    });

    // Mock ClipboardItem - use a class so it can be called with `new`
    // @ts-expect-error - ClipboardItem types not exact
    global.ClipboardItem = class MockClipboardItem {
      types: string[];
      _data: Record<string, unknown>;
      constructor(data: Record<string, unknown>) {
        this._data = data;
        this.types = Object.keys(data);
      }
      getType(type: string): Promise<Blob> {
        const value = this._data[type];
        if (value instanceof Blob) {
          return Promise.resolve(value);
        }
        return Promise.resolve(
          new Blob([String(value || "")], { type }),
        );
      }
      static supports = vi.fn().mockReturnValue(true);
    };

    // Don't mock Blob - use the real one from jsdom/node
    // Tests that need Blob will use the real implementation

    return mockClipboard;
  },

  localStorage: () => {
    const store: Record<string, string> = {};

    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn((key: string) => store[key] || null),
        setItem: vi.fn((key: string, value: string) => {
          store[key] = value;
        }),
        removeItem: vi.fn((key: string) => {
          // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
          delete store[key];
        }),
        clear: vi.fn(() => {
          for (const key of Object.keys(store)) {
            // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
            delete store[key];
          }
        }),
        key: vi.fn((index: number) => Object.keys(store)[index] || null),
        get length() {
          return Object.keys(store).length;
        },
      },
      writable: true,
    });
  },

  fetch: (mockImplementation?: Mock) => {
    const mockFetch = vi.fn(mockImplementation);
    global.fetch = mockFetch;
    return mockFetch;
  },

  websocket: () => {
    const mockWs = {
      close: vi.fn(),
      send: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      onopen: null,
      onclose: null,
      onmessage: null,
      onerror: null,
      readyState: WebSocket.CONNECTING,
    };

    global.WebSocket = vi.fn(() => mockWs) as unknown as typeof WebSocket;
    return mockWs;
  },
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function asMock<T extends (...args: any[]) => unknown>(fn: T): Mock<T> {
  invariant(
    "mock" in fn,
    "fn must be a mock function, use vi.fn() to create one",
  );
  return fn as unknown as Mock<T>;
}

export function partialImplementation<T extends object>(
  partial: Partial<T>,
): T {
  return partial as unknown as T;
}
