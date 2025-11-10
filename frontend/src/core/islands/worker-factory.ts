/* Copyright 2024 Marimo. All rights reserved. */

import { getMarimoVersion } from "../meta/globals";
import workerUrl from "./worker/worker.tsx?worker&url";

/**
 * Interface for creating Web Workers for islands
 */
export interface WorkerFactory {
  /**
   * Creates a new worker instance
   */
  create(): Worker;
}

/**
 * Configuration for the default worker factory
 */
export interface DefaultWorkerFactoryConfig {
  /**
   * The URL to the worker script
   * Defaults to the bundled worker
   */
  workerUrl?: string;

  /**
   * The name to give the worker (shows in DevTools)
   * Defaults to the marimo version
   */
  workerName?: string;
}

/**
 * Default implementation of WorkerFactory that creates Pyodide workers
 * for islands mode.
 */
export class DefaultWorkerFactory implements WorkerFactory {
  private readonly url: string;
  private readonly name: string;

  constructor(config: DefaultWorkerFactoryConfig = {}) {
    this.url = config.workerUrl || this.getDefaultWorkerUrl();
    this.name = config.workerName || getMarimoVersion();
  }

  /**
   * Creates a new Pyodide worker
   */
  create(): Worker {
    const js = `import ${JSON.stringify(new URL(this.url, import.meta.url))}`;
    const blob = new Blob([js], { type: "application/javascript" });
    const objURL = URL.createObjectURL(blob);

    const worker = new Worker(objURL, {
      type: "module",
      /* @vite-ignore */
      name: this.name,
    });

    // Clean up blob URL on error
    worker.addEventListener("error", () => {
      URL.revokeObjectURL(objURL);
    });

    return worker;
  }

  /**
   * Gets the default worker URL based on environment
   */
  private getDefaultWorkerUrl(): string {
    const url = import.meta.env.DEV
      ? workerUrl
      : makeRelativeWorkerUrl(workerUrl);
    return url;
  }
}

/**
 * Makes worker URLs relative for production builds
 */
function makeRelativeWorkerUrl(url: string): string {
  return url.startsWith("./")
    ? url
    : url.startsWith("/")
      ? `.${url}`
      : `./${url}`;
}

/**
 * Mock worker factory for testing
 */
export class MockWorkerFactory implements WorkerFactory {
  public workers: Worker[] = [];
  private readonly mockWorker?: Worker;

  constructor(mockWorker?: Worker) {
    this.mockWorker = mockWorker;
  }

  create(): Worker {
    const worker = this.mockWorker || this.createMockWorker();
    this.workers.push(worker);
    return worker;
  }

  private createMockWorker(): Worker {
    // Create a minimal mock worker
    return {
      postMessage: () => {},
      terminate: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => true,
      onmessage: null,
      onerror: null,
      onmessageerror: null,
    } as unknown as Worker;
  }

  /**
   * Gets all workers created by this factory
   */
  getCreatedWorkers(): Worker[] {
    return this.workers;
  }

  /**
   * Terminates all workers created by this factory
   */
  terminateAll(): void {
    for (const worker of this.workers) {
      worker.terminate();
    }
    this.workers = [];
  }
}
