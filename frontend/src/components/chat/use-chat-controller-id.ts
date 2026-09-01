/* Copyright 2026 Marimo. All rights reserved. */

import { useState } from "react";
import useEvent from "react-use-event-hook";
import type { ChatId } from "@/core/ai/state";
import { generateUUID } from "@/utils/uuid";

function generateChatId(): ChatId {
  return generateUUID() as ChatId;
}

/**
 * Keep an ID for an unsaved chat so `useChat` can distinguish it from the
 * previously active chat. Empty chats are not added to chat history.
 */
export function useChatControllerId(activeChatId?: ChatId) {
  const [draftChatId, setDraftChatId] = useState(generateChatId);
  const renewDraftChatId = useEvent(() => setDraftChatId(generateChatId()));

  return {
    chatControllerId: activeChatId ?? draftChatId,
    renewDraftChatId,
  };
}
