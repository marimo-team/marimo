/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Loader2Icon, PartyPopperIcon } from "lucide-react";
import { PanelEmptyState } from "./empty-state";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { Snippet } from "@/core/network/types";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { readSnippets } from "@/core/network/requests";

export const SnippetsPanel: React.FC = () => {
  const [selectedSnippet, setSelectedSnippet] = React.useState<Snippet>();
  const {
    data: snippets,
    error,
    loading,
  } = useAsyncData(() => {
    return readSnippets();
  }, []);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (loading || !snippets) {
    return <Loader2Icon className="animate-spin h-6 w-6" />;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-1">
        <SnippetList
          onSelect={(snippet) => setSelectedSnippet(snippet)}
          snippets={snippets.snippets}
        />
      </div>
      <div className="flex flex-1">
        {selectedSnippet ? (
          <SnippetViewer snippet={selectedSnippet} />
        ) : (
          <PanelEmptyState
            title="No snippet selected"
            description="Click on a snippet to view its content."
            icon={<PartyPopperIcon />}
          />
        )}
      </div>
    </div>
  );
};

const SnippetViewer: React.FC<{ snippet: Snippet }> = ({ snippet }) => {
  return (
    <div className="px-2 py-1">
      <div className="text-xs font-mono font-semibold bg-muted border-y px-2 py-1">
        {snippet.title}
      </div>
      <div className="px-2">
        {snippet.sections.map((section, idx) => {
          if (section.html) {
            return <div key={idx}>{renderHTML({ html: section.html })}</div>;
          }
          return <pre key={idx}>{section.code}</pre>;
        })}
      </div>
    </div>
  );
};

const SnippetList: React.FC<{
  onSelect: (snippet: Snippet) => void;
  snippets: Snippet[];
}> = ({ snippets, onSelect }) => {
  return (
    <div className="flex flex-col overflow-auto">
      {snippets.map((snippet) => (
        <div
          key={snippet.title}
          className="cursor-pointer hover:bg-gray-100"
          onClick={() => onSelect(snippet)}
        >
          <SnippetListItem key={snippet.title} snippet={snippet} />
        </div>
      ))}
    </div>
  );
};

const SnippetListItem: React.FC<{ snippet: Snippet }> = ({ snippet }) => {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-row gap-2 items-center">
        <span className="mt-1 text-accent-foreground">{snippet.title}</span>
      </div>
    </div>
  );
};
