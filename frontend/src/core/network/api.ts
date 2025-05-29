/* Copyright 2024 Marimo. All rights reserved. */
import { once } from "@/utils/once";
import { Logger } from "../../utils/Logger";
import { getSessionId } from "../kernel/session";
import { createMarimoClient } from "@marimo-team/marimo-api";
import { store } from "@/core/state/jotai";
import { serverTokenAtom } from "@/core/meta/state";
import { assertExists } from "@/utils/assertExists";

const getServerTokenOnce = once(() => {
  const token = store.get(serverTokenAtom);
  assertExists(token, "internal-error: server token not found");
  return token;
});

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
    return {
      "Marimo-Session-Id": getSessionId(),
      "Marimo-Server-Token": getServerTokenOnce(),
    };
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

export const marimoClient = createMarimoClient({
  // eslint-disable-next-line ssr-friendly/no-dom-globals-in-module-scope
  baseUrl:
    typeof document === "undefined"
      ? undefined
      : getBaseUriWithoutQueryParams(),
});

marimoClient.use({
  onRequest: (req) => {
    for (const [key, value] of Object.entries(API.headers())) {
      req.headers.set(key, value);
    }
    return req;
  },
});
