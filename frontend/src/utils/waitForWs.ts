/* Copyright 2023 Marimo. All rights reserved. */

/**
 * Wait for a websocket to be available, with linear backoff.
 */
export async function waitForWs(url: string, tries = 10) {
  for (let i = 0; i < tries; i++) {
    try {
      return await tryConnection(url);
    } catch {
      // wait a second * i
      // linear backoff
      await new Promise((resolve) => setTimeout(resolve, 1000 * (i + 1)));
    }
  }
  throw new Error(`Failed to connect to ${url}`);
}

async function tryConnection(url: string) {
  return new Promise<string>((resolve, reject) => {
    const ws = new WebSocket(url);
    ws.onopen = () => {
      ws.close();
      resolve(url);
    };
    ws.onerror = (err) => {
      ws.close();
      reject(err);
    };
  });
}
