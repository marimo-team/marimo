/* Copyright 2026 Marimo. All rights reserved. */
import { ArrowDownIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { useId, useLayoutEffect, useRef, useState } from "react";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { useEventListener } from "@/hooks/useEventListener";
import { cn } from "@/utils/cn";

function hasSelection(element: HTMLElement) {
  const selection = element.ownerDocument.getSelection();
  return (
    selection && !selection.isCollapsed && selection.containsNode(element, true)
  );
}

export function StartupOutput({
  logs,
  label,
}: {
  logs: string;
  label: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [following, setFollowing] = useState(true);
  const outputRef = useRef<HTMLPreElement>(null);
  const outputId = useId();
  const lines = logs.trimEnd().split(/\r?\n/);

  useEventListener(document, "selectionchange", () => {
    if (outputRef.current && hasSelection(outputRef.current)) {
      setFollowing(false);
    }
  });

  useLayoutEffect(() => {
    const output = outputRef.current;
    if (!output) {
      return;
    }
    const previous = output.textContent ?? "";
    // Append without replacing selected text nodes as more output arrives.
    if (logs.startsWith(previous)) {
      if (logs.length > previous.length) {
        output.append(document.createTextNode(logs.slice(previous.length)));
      }
    } else {
      output.textContent = logs;
    }
    if (expanded && following && !hasSelection(output)) {
      output.scrollTop = output.scrollHeight;
    }
  }, [logs, expanded, following]);

  if (!logs.trim()) {
    return null;
  }

  return (
    <div className="relative mt-2.5 min-w-0 contain-inline-size rounded border bg-muted/30 text-muted-foreground">
      <div className={cn(expanded && "flex items-center pr-1")}>
        <button
          type="button"
          aria-label={`${expanded ? "Collapse" : "Expand"} ${label}`}
          aria-expanded={expanded}
          aria-controls={outputId}
          title={expanded ? "Collapse output" : "Expand output"}
          className={cn(
            "flex w-full min-w-0 items-start gap-2 px-2.5 py-1 text-left rounded hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring",
            expanded && "items-center justify-between text-xs",
          )}
          onClick={() => {
            setExpanded(!expanded);
            setFollowing(true);
          }}
        >
          {expanded ? (
            <>
              <span>
                {lines.length} {lines.length === 1 ? "line" : "lines"}
              </span>
              <ChevronUpIcon className="size-3.5 shrink-0" aria-hidden={true} />
            </>
          ) : (
            <>
              <span
                className="min-w-0 flex-1 font-mono text-[11px] leading-5"
                aria-hidden={true}
              >
                {lines.slice(-3).map((line, index) => (
                  <span
                    key={index}
                    className="block truncate opacity-60 last:opacity-100"
                  >
                    {line || "\u00A0"}
                  </span>
                ))}
              </span>
              <ChevronDownIcon
                className="size-3.5 shrink-0 mt-0.5 opacity-60"
                aria-hidden={true}
              />
            </>
          )}
        </button>
        {expanded && (
          <CopyClipboardIcon
            value={logs}
            ariaLabel={`Copy ${label}`}
            tooltip="Copy output"
            className="size-3.5"
            buttonClassName="size-6 shrink-0 flex items-center justify-center rounded hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring"
          />
        )}
      </div>
      <pre
        id={outputId}
        ref={outputRef}
        hidden={!expanded}
        tabIndex={0}
        aria-label={label}
        className="max-h-48 overflow-auto overscroll-contain whitespace-pre px-2.5 pb-2.5 font-mono text-[11px] leading-5 scrollbar-thin focus-visible:outline-2 focus-visible:outline-ring"
        onScroll={(event) => {
          const output = event.currentTarget;
          setFollowing(
            !hasSelection(output) &&
              output.scrollHeight - output.scrollTop - output.clientHeight < 12,
          );
        }}
      />
      {expanded && !following && (
        <button
          type="button"
          className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-1 whitespace-nowrap rounded-full border bg-background px-2 py-1 text-xs shadow-xs hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
          onClick={() => {
            const output = outputRef.current;
            if (output) {
              if (hasSelection(output)) {
                output.ownerDocument.getSelection()?.removeAllRanges();
              }
              output.focus({ preventScroll: true });
            }
            setFollowing(true);
          }}
        >
          <ArrowDownIcon className="size-3" aria-hidden={true} />
          Jump to latest
        </button>
      )}
    </div>
  );
}
