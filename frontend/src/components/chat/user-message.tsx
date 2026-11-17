/* Copyright 2026 Marimo. All rights reserved. */

import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import type { FileUIPart, TextUIPart, UIMessage } from "ai";
import { PencilIcon } from "lucide-react";
import React from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { focusInputAndMoveToEnd } from "@/core/codemirror/utils";
import { PromptInput } from "../editor/ai/prompt-input";
import { CopyClipboardIcon } from "../icons/copy-icon";
import { AttachmentRenderer } from "./chat-components";

interface UserMessageProps {
  message: UIMessage;
  canEdit: boolean;
  onEdit: (newValue: string) => Promise<boolean>;
}

export const UserMessage: React.FC<UserMessageProps> = ({
  message,
  canEdit,
  onEdit,
}) => {
  const content = message.parts
    .filter((p): p is TextUIPart => p.type === "text")
    .map((p) => p.text)
    .join("\n");
  const attachments = message.parts
    .filter((p): p is FileUIPart => p.type === "file")
    .map((part, idx) => (
      // Sent parts never reorder, and a file attached twice repeats its URL.
      // react-doctor-disable-next-line react-doctor/no-array-index-as-key
      <AttachmentRenderer attachment={part} key={idx} />
    ));

  const [draft, setDraft] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const inputRef = React.useRef<ReactCodeMirrorRef>(null);
  const editButtonRef = React.useRef<HTMLButtonElement>(null);
  const editing = draft != null;

  const startEditing = () => {
    setDraft(content);
    focusInputAndMoveToEnd(inputRef);
  };

  const cancel = () => {
    setDraft(null);
    requestAnimationFrame(() => editButtonRef.current?.focus());
  };

  const submit = async (value: string) => {
    if (!canEdit || isSubmitting || !value.trim()) {
      return;
    }
    setIsSubmitting(true);
    try {
      if (await onEdit(value)) {
        setDraft((current) => (current === value ? null : current));
      }
    } catch (error) {
      setIsSubmitting(false);
      throw error;
    }
    setIsSubmitting(false);
  };

  if (editing) {
    return (
      <div className="w-full rounded-[10px] border border-border bg-background">
        {attachments}
        <div className="px-2 py-1.5">
          <PromptInput
            inputRef={inputRef}
            className="max-h-[400px]"
            value={draft}
            onChange={setDraft}
            onSubmit={(_e, value) => submit(value)}
            onClose={cancel}
            placeholder="Type your message. Use @ to reference variables and cells."
          />
        </div>
        <div className="flex items-center gap-2 border-t border-border/20 px-3 py-1.5">
          <span className="mr-auto text-xs text-muted-foreground">
            Responses after this message will be replaced.
          </span>
          <Button variant="text" size="xs" onClick={cancel}>
            Cancel
          </Button>
          <Button
            size="xs"
            disabled={!canEdit || isSubmitting || !draft.trim()}
            onClick={() => submit(draft)}
          >
            Send
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex max-w-[90%] flex-col items-end gap-1">
      {attachments}
      <div className="rounded-[10px] bg-(--slate-3) px-3 py-1.5 whitespace-pre-wrap wrap-break-word">
        <MentionText text={content} />
      </div>
      <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        <Tooltip content="Edit">
          <Button
            ref={editButtonRef}
            variant="text"
            size="icon"
            aria-label="Edit message"
            className="chat-control"
            disabled={!canEdit}
            onClick={startEditing}
          >
            <PencilIcon className="size-3" />
          </Button>
        </Tooltip>
        <CopyClipboardIcon
          value={content}
          className="size-3"
          buttonClassName="chat-control flex size-6 items-center justify-center rounded-md"
        />
      </div>
    </div>
  );
};

const MENTION = /([@#])[\w-]+:\/\/([\w./-]+)/g;

const MentionText: React.FC<{ text: string }> = ({ text }) => {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(MENTION)) {
    nodes.push(text.slice(last, match.index));
    nodes.push(
      <span
        key={match.index}
        title={match[0].slice(1)}
        className="rounded-sm bg-(--slate-5) px-1 font-mono text-[0.85em]"
      >
        {match[1]}
        {match[2]}
      </span>,
    );
    last = match.index + match[0].length;
  }
  nodes.push(text.slice(last));
  return nodes;
};
