/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import {
  BetweenHorizonalStartIcon,
  Loader2Icon,
  PartyPopperIcon,
} from "lucide-react";
import { PanelEmptyState } from "./empty-state";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { Snippet } from "@/core/network/types";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { readSnippets } from "@/core/network/requests";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import { CommandList } from "cmdk";

import "./snippets-panel.css";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { useTheme } from "@/theme/useTheme";
import { EditorView } from "@codemirror/view";
import { Suspense } from "react";
import AnyLanguageCodeMirror from "@/plugins/impl/code/any-language-editor";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";

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
    <div className="flex-1 overflow-hidden">
      <Command className="h-1/3 border-b rounded-none">
        <CommandInput placeholder="Search snippets..." className="h-6 m-1" />
        <CommandEmpty>No results</CommandEmpty>
        <SnippetList
          onSelect={(snippet) => setSelectedSnippet(snippet)}
          snippets={snippets.snippets}
        />
      </Command>
      <Suspense>
        <div className="h-2/3 snippet-viewer flex flex-col">
          {selectedSnippet ? (
            <SnippetViewer
              key={selectedSnippet.title}
              snippet={selectedSnippet}
            />
          ) : (
            <PanelEmptyState
              title="No snippet selected"
              description="Click on a snippet to view its content."
              icon={<PartyPopperIcon />}
            />
          )}
        </div>
      </Suspense>
    </div>
  );
};

const SnippetViewer: React.FC<{ snippet: Snippet }> = ({ snippet }) => {
  const { theme } = useTheme();
  return (
    <>
      <div className="text-sm font-semibold bg-muted border-y px-2 py-1">
        {snippet.title}
      </div>
      <div className="px-2 py-1 space-y-4 overflow-auto flex-1">
        {snippet.sections.map((section) => {
          if (section.html) {
            return (
              <div key={`${snippet.title}-${section.id}`}>
                {renderHTML({ html: section.html })}
              </div>
            );
          }
          return (
            <div
              className="relative hover-actions-parent px-2"
              key={`${snippet.title}-${section.id}`}
            >
              <Tooltip content="Insert snippet">
                <Button
                  className="absolute -top-2 -right-1 z-10 hover-action px-2"
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    // TODO: Insert code into editor
                  }}
                >
                  <BetweenHorizonalStartIcon className="h-5 w-5" />
                </Button>
              </Tooltip>
              <AnyLanguageCodeMirror
                key={`${snippet.title}-${section.id}`}
                theme={theme === "dark" ? "dark" : "light"}
                language="python"
                className="border rounded overflow-hidden"
                extensions={[EditorView.lineWrapping]}
                value={section.code}
                readOnly={true}
              />
            </div>
          );
        })}
      </div>
    </>
  );
};

const SnippetList: React.FC<{
  onSelect: (snippet: Snippet) => void;
  snippets: Snippet[];
}> = ({ snippets, onSelect }) => {
  return (
    <CommandList className="flex flex-col overflow-auto">
      {snippets.map((snippet) => (
        <CommandItem
          className="rounded-none"
          key={snippet.title}
          onSelect={() => onSelect(snippet)}
        >
          <div className="flex flex-row gap-2 items-center">
            <span className="mt-1 text-accent-foreground">{snippet.title}</span>
          </div>
        </CommandItem>
      ))}
    </CommandList>
  );
};
