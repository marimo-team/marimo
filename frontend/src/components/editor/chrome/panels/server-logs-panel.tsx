/* Copyright 2026 Marimo. All rights reserved. */

import { RefreshCwIcon, ServerIcon } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useInterval } from "@/hooks/useInterval";
import { PanelEmptyState } from "./empty-state";

const REFRESH_INTERVAL_MS = 10000; // 10 seconds

async function fetchLogFiles(): Promise<string[]> {
  const res = await fetch("/api/logs/list");
  const data: { files: string[] } = await res.json();
  return data.files ?? [];
}

async function fetchLogContent(filename: string): Promise<string> {
  const res = await fetch(`/api/logs/${encodeURIComponent(filename)}`);
  return res.text();
}

const ServerLogsPanel: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<string>("");
  const preRef = useRef<HTMLPreElement>(null);

  const { data: files, isPending: filesLoading } = useAsyncData(
    fetchLogFiles,
    [],
  );

  if (files && files.length > 0 && !selectedFile) {
    setSelectedFile(files.includes("marimo.log") ? "marimo.log" : files[0]);
  }

  const {
    data: content,
    isPending: contentLoading,
    refetch,
  } = useAsyncData(
    async () => (selectedFile ? fetchLogContent(selectedFile) : ""),
    [selectedFile],
  );

  // Auto-scroll to bottom when content changes
  useEffect(() => {
    if (preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [content]);

  // Refetch every 10 seconds
  useInterval(() => refetch(), {
    delayMs: REFRESH_INTERVAL_MS,
    whenVisible: true,
  });

  if (!filesLoading && (!files || files.length === 0)) {
    return (
      <PanelEmptyState
        title="No server logs"
        description="No log files found in the server log directory."
        icon={<ServerIcon />}
      />
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex flex-row items-center gap-2 px-2 py-1 border-b shrink-0">
        {files && files.length > 1 && (
          <select
            className="text-xs border rounded px-1 py-0.5 bg-background"
            value={selectedFile}
            onChange={(e) => setSelectedFile(e.target.value)}
          >
            {files.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        )}
        {files && files.length === 1 && (
          <span className="text-xs text-muted-foreground">{selectedFile}</span>
        )}
        <Button size="xs" variant="text" onClick={refetch}>
          <RefreshCwIcon className="w-3 h-3" />
          Refresh
        </Button>
      </div>
      <pre
        ref={preRef}
        className="flex-1 overflow-auto text-xs font-mono p-2 whitespace-pre-wrap"
      >
        {contentLoading ? "Loading..." : content}
      </pre>
    </div>
  );
};

export default ServerLogsPanel;
