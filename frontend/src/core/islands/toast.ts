/* Copyright 2026 Marimo. All rights reserved. */
let didToast = false;
let toastElement: HTMLDivElement | undefined;

/**
 * Show a toast message in the center of the screen.
 *
 * Intentionally outside React and not using our styles since we place
 * this in the global scope.
 *
 * We only show this once.
 */
export function toastIslandsLoading() {
  if (didToast) {
    return;
  }
  didToast = true;
  toastElement = document.createElement("div");
  toastElement.classList.add("marimo-islands-loading-toast");
  toastElement.textContent = "⚡ reactivity initializing...";
  toastElement.style.position = "fixed";
  toastElement.style.top = "0.5rem";
  toastElement.style.left = "50%";
  toastElement.style.transform = "translateX(-50%)";
  toastElement.style.zIndex = "1000";
  toastElement.style.backgroundColor = "#0f172a";
  toastElement.style.color = "#f8fafc";
  toastElement.style.padding = "0.25rem 0.5rem";
  toastElement.style.borderRadius = "0.5rem";
  toastElement.style.fontSize = "0.875rem";
  document.body.append(toastElement);
}

/**
 * Remove the toast message from the screen.
 */
export function dismissIslandsLoadingToast() {
  if (toastElement) {
    toastElement.remove();
  }
}
