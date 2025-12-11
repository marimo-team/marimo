/* Copyright 2024 Marimo. All rights reserved. */

import type { SignalListenerHandler } from "vega-typings";

export interface SignalListener {
  signalName: string;
  handler: SignalListenerHandler;
}
