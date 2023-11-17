/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable no-restricted-globals */
/* eslint-disable ssr-friendly/no-dom-globals-in-module-scope */

import { jsonParseWithSpecialChar } from "./json-parser";

self.onmessage = (e: MessageEvent) => {
  const data = e.data;
  const json = jsonParseWithSpecialChar(data);
  self.postMessage(json);
  self.close();
};
