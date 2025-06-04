/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "../../utils/Logger";
import { createMarimoClient } from "@marimo-team/marimo-api";
import { store } from "@/core/state/jotai";
import { runtimeManagerAtom } from "../runtime/config";
import type { RuntimeManager } from "../runtime/runtime";

function getBaseUriWithoutQueryParams(): string {
  // Remove query params and hash
  const url = new URL(document.baseURI);
  url.search = "";
  url.hash = "";
  return url.toString();
}

/**
 * Wrapper around fetch that adds XSRF token and session ID to the request and
 * strong types.
 */
export const API = {
  post<REQ, RESP = null>(
    url: string,
    body: REQ,
    opts: {
      headers?: Record<string, string>;
      baseUrl?: string;
    } = {},
  ): Promise<RESP> {
    const baseUrl = opts.baseUrl ?? getBaseUriWithoutQueryParams();
    const fullUrl = `${baseUrl}api${url}`;
    return fetch(fullUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...API.headers(),
        ...opts.headers,
      },
      body: JSON.stringify(body),
    })
      .then(async (response) => {
        const isJson = response.headers
          .get("Content-Type")
          ?.startsWith("application/json");
        if (!response.ok) {
          const errorBody = isJson
            ? await response.json()
            : await response.text();
          throw new Error(response.statusText, { cause: errorBody });
        }
        if (isJson) {
          return response.json() as RESP;
        }
        return response.text() as unknown as RESP;
      })
      .catch((error) => {
        // Catch and rethrow
        Logger.error(`Error requesting ${fullUrl}`, error);
        throw error;
      });
  },
  get<RESP = null>(
    url: string,
    opts: {
      headers?: Record<string, string>;
      baseUrl?: string;
    } = {},
  ): Promise<RESP> {
    const baseUrl = opts.baseUrl ?? getBaseUriWithoutQueryParams();
    const fullUrl = `${baseUrl}api${url}`;
    return fetch(fullUrl, {
      method: "GET",
      headers: {
        ...API.headers(),
        ...opts.headers,
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(response.statusText);
        }
        if (
          response.headers.get("Content-Type")?.startsWith("application/json")
        ) {
          return response.json() as RESP;
        }
        return null as RESP;
      })
      .catch((error) => {
        // Catch and rethrow
        Logger.error(`Error requesting ${fullUrl}`, error);
        throw error;
      });
  },
  headers() {
    const runtimeManager = store.get(runtimeManagerAtom);
    return runtimeManager.headers();
  },
  handleResponse: <T>(response: {
    data?: T | undefined;
    error?: Record<string, unknown>;
    response: Response;
  }): Promise<T> => {
    if (response.error) {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      return Promise.reject(response.error);
    }
    return Promise.resolve(response.data as T);
  },
  handleResponseReturnNull: (response: {
    error?: Record<string, unknown>;
    response: Response;
  }): Promise<null> => {
    if (response.error) {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      return Promise.reject(response.error);
    }
    return Promise.resolve(null);
  },
};

export function createClientWithRuntimeManager(runtimeManager: RuntimeManager) {
  const marimoClient = createMarimoClient({
    baseUrl: runtimeManager.httpURL.toString(),
  });

  marimoClient.use({
    onRequest: (req) => {
      const runtimeManager = store.get(runtimeManagerAtom);
      const headers = runtimeManager.headers();

      for (const [key, value] of Object.entries(headers)) {
        req.headers.set(key, value);
      }
      return req;
    },
  });

  return marimoClient;
}
