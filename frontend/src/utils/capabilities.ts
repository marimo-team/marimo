/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "./Logger";
import { once } from "./once";

/**
 * Capabilities that may be restricted in sandboxed iframes
 */
export interface IframeCapabilities {
  /** Whether the app is running inside an iframe */
  isEmbedded: boolean;
  /** Whether localStorage is available */
  hasLocalStorage: boolean;
  /** Whether sessionStorage is available */
  hasSessionStorage: boolean;
  /** Whether the Clipboard API is available */
  hasClipboard: boolean;
  /** Whether downloads are likely to work */
  hasDownloads: boolean;
  /** Whether fullscreen API is available */
  hasFullscreen: boolean;
  /** Whether media devices (microphone/camera) may be accessible */
  hasMediaDevices: boolean;
}

/**
 * Test if a specific storage type is available and working
 */
function testStorage(type: "localStorage" | "sessionStorage"): boolean {
  try {
    const storage: Storage = window[type];
    const testKey = "__storage_test__";
    const testValue = "test";

    if (!storage) {
      return false;
    }

    storage.setItem(testKey, testValue);
    const retrieved = storage.getItem(testKey);
    storage.removeItem(testKey);

    return retrieved === testValue;
  } catch {
    return false;
  }
}

/**
 * Test if downloads are likely to work
 * This is a heuristic check - actual downloads may still fail
 */
function testDownloadCapability(): boolean {
  try {
    // Check if we can create anchor elements with download attribute
    const a = document.createElement("a");
    return "download" in a;
  } catch {
    return false;
  }
}

/**
 * Detect all iframe capabilities at once
 * This should be called once at startup and cached
 */
function detectIframeCapabilities(): IframeCapabilities {
  const isEmbedded = window.parent !== window;

  const capabilities: IframeCapabilities = {
    isEmbedded,
    hasLocalStorage: testStorage("localStorage"),
    hasSessionStorage: testStorage("sessionStorage"),
    hasClipboard: navigator.clipboard !== undefined,
    hasDownloads: testDownloadCapability(),
    hasFullscreen:
      document.fullscreenEnabled !== undefined && document.fullscreenEnabled,
    hasMediaDevices:
      navigator.mediaDevices !== undefined &&
      typeof navigator.mediaDevices.getUserMedia === "function",
  };

  // Log warnings for missing capabilities when embedded
  if (isEmbedded) {
    Logger.log("[iframe] Running in embedded context");

    if (!capabilities.hasLocalStorage) {
      Logger.warn("[iframe] localStorage unavailable - using fallback storage");
    }

    if (!capabilities.hasClipboard) {
      Logger.warn("[iframe] Clipboard API unavailable");
    }

    if (!capabilities.hasDownloads) {
      Logger.warn("[iframe] Download capability may be restricted");
    }

    if (!capabilities.hasFullscreen) {
      Logger.warn("[iframe] Fullscreen API unavailable");
    }

    if (!capabilities.hasMediaDevices) {
      Logger.warn("[iframe] Media devices API unavailable");
    }
  }

  return capabilities;
}

/**
 * Get the current iframe capabilities (cached after first call)
 */
export const getIframeCapabilities = once(() => detectIframeCapabilities());
