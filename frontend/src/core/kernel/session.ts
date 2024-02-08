/* Copyright 2024 Marimo. All rights reserved. */
import { generateUUID } from "@/utils/uuid";
import { TypedString } from "@/utils/typed";

export type SessionId = TypedString<"SessionId">;

const sessionId = generateUUID() as SessionId;

/**
 * Resume an existing session or start a new one
 */
export function getSessionId(): SessionId {
  return sessionId;
}
