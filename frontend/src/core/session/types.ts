/* Copyright 2026 Marimo. All rights reserved. */

import type { ConnectionStatus as HostConnectionStatus } from "../notebook/replica";
import type { NotificationMessageData } from "../kernel/messages";

export {
  ConnectionState,
  ConnectionClosedReason as WebSocketClosedReason,
} from "../notebook/replica";

export type ConnectionPhase =
  | NotificationMessageData<"startup-progress">["phase"]
  | "reconnecting";

export type ConnectionStatus = HostConnectionStatus & {
  phase?: ConnectionPhase;
};
