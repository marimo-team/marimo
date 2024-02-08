/* Copyright 2024 Marimo. All rights reserved. */
import { once } from "@/utils/once";
import { Logger } from "../../utils/Logger";
import { getMarimoServerToken } from "../dom/marimo-tag";
import { getSessionId } from "../kernel/session";

export function getXsrfCookie(): string {
  const r = document.cookie.match("\\b_xsrf=([^;]*)\\b");
  return r ? r[1] : "";
}

const getServerTokenOnce = once(() => {
  return getMarimoServerToken();
});

/**
 * Wrapper around fetch that adds XSRF token and session ID to the request and
 * strong types.
 */
export const API = {
  post<REQ, RESP = null>(url: string, body: REQ): Promise<RESP> {
    const BASE_URL = `${document.baseURI}api`;

    const fullUrl = BASE_URL + url;
    return fetch(fullUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Xsrftoken": getXsrfCookie(),
        "Marimo-Session-Id": getSessionId(),
        "Marimo-Server-Token": getServerTokenOnce(),
      },
      body: JSON.stringify(body),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(response.statusText);
        } else if (
          response.headers.get("Content-Type")?.startsWith("application/json")
        ) {
          return response.json() as RESP;
        } else {
          return null as RESP;
        }
      })
      .catch((error) => {
        // Catch and rethrow
        Logger.error(`Error requesting ${fullUrl}`, error);
        throw error;
      });
  },
};
