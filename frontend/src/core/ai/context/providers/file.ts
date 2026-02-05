/* Copyright 2026 Marimo. All rights reserved. */

import {
  type Completion,
  type CompletionContext,
  type CompletionResult,
  type CompletionSource,
  closeCompletion,
} from "@codemirror/autocomplete";
import { toast } from "@/components/ui/use-toast";
import { contextCallbacks } from "@/core/codemirror/ai/state";
import type { EditRequests, FileInfo, RunRequests } from "@/core/network/types";
import { deserializeBlob } from "@/utils/blob";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { type AIContextItem, AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Boosts, Sections } from "./common";
export interface FileContextItem extends AIContextItem {
  type: "file";
  data: {
    path: string;
    isDirectory: boolean;
  };
}

export interface FileSearchConfig {
  maxDepth: number;
  maxResults: number;
  defaultResultsLimit: number;
  includeDirectories: boolean;
}

const DEFAULT_FILE_SEARCH_CONFIG: FileSearchConfig = {
  maxDepth: 3,
  maxResults: 20,
  defaultResultsLimit: 5,
  includeDirectories: false,
};

export class FileContextProvider extends AIContextProvider<FileContextItem> {
  readonly title = "Files";
  readonly mentionPrefix = "#";
  readonly contextType = "file";

  private apiRequests: EditRequests & RunRequests;
  private config: FileSearchConfig;

  constructor(
    apiRequests: EditRequests & RunRequests,
    config: FileSearchConfig = DEFAULT_FILE_SEARCH_CONFIG,
  ) {
    super();
    this.apiRequests = apiRequests;
    this.config = config;
  }

  /**
   * Create a dynamic completion source for file mentions
   * This bypasses the standard registry system to enable dynamic searching
   */
  createCompletionSource(): CompletionSource {
    return async (
      context: CompletionContext,
    ): Promise<CompletionResult | null> => {
      // Look for # followed by any characters (including dots, slashes, etc.)
      const match = context.matchBefore(/#[^\s#]*/);
      if (!match) {
        return null;
      }

      const matchText = match.text;
      if (!matchText.startsWith("#")) {
        return null;
      }

      const searchQuery = matchText.slice(1); // Remove the #
      if (searchQuery.length === 0) {
        // Show some popular files/directories even with no query
        return this.getDefaultCompletions(match);
      }

      try {
        const files = (await this.searchFiles(searchQuery)) || [];
        const completions = files.map((file: FileInfo) => {
          const item: FileContextItem = {
            uri: this.asURI(file.path),
            name: file.name,
            type: this.contextType,
            description: file.isDirectory ? "Directory" : "File",
            data: {
              path: file.path,
              isDirectory: file.isDirectory,
            },
          };
          return this.formatCompletion(item);
        });

        return {
          from: match.from,
          options: completions,
        };
      } catch (error) {
        Logger.error("Failed to search files:", error);
        return null;
      }
    };
  }

  private searchFiles = async (
    query: string,
    options: Partial<FileSearchConfig> = {},
  ): Promise<FileInfo[]> => {
    const { maxDepth, maxResults, includeDirectories } = {
      ...this.config,
      ...options,
    };
    const response = await this.apiRequests.sendSearchFiles({
      query,
      includeFiles: true,
      includeDirectories: includeDirectories,
      depth: maxDepth,
      limit: maxResults,
    });
    return response.files;
  };

  private async getDefaultCompletions(match: {
    from: number;
  }): Promise<CompletionResult | null> {
    try {
      // Show common file types when no specific query is given
      // Use broad searches for common file types
      const searches = ["py", "md", "csv"];

      // Try the first search that returns results
      for (const search of searches) {
        try {
          const files = await this.searchFiles(search, {
            maxDepth: 1,
            maxResults: 5,
          });

          if (files && files.length > 0) {
            const completions = files.map((file) => {
              const item: FileContextItem = {
                uri: this.asURI(file.path),
                name: file.name,
                type: this.contextType,
                description: file.isDirectory ? "Directory" : "File",
                data: {
                  path: file.path,
                  isDirectory: file.isDirectory,
                },
              };
              return this.formatCompletion(item);
            });

            return {
              from: match.from,
              options: completions,
            };
          }
        } catch (error) {
          Logger.error("Failed to get default file completions:", error);
        }
      }

      // If no searches return results, return empty
      return {
        from: match.from,
        options: [],
      };
    } catch (error) {
      Logger.error("Failed to get default file completions:", error);
      return null;
    }
  }

  getItems(): FileContextItem[] {
    // Files are fetched dynamically, so return empty array
    // This provider relies on dynamic fetching via createCompletionSource()
    return [];
  }

  formatCompletion(item: FileContextItem): Completion {
    const { data, name } = item;
    const icon = data.isDirectory ? "📁" : "📄";

    return {
      ...this.createBasicCompletion(item),
      type: "file",
      section: Sections.FILE,
      boost: data.isDirectory ? Boosts.MEDIUM : Boosts.LOW,
      detail: data.path,
      displayLabel: `${icon} ${name}`,
      apply: async (view, completion, from, to) => {
        // First try to add the file as an attachment, if the callback is provided
        // otherwise add it to the prompt
        const addAttachment = view.state.facet(contextCallbacks)?.addAttachment;
        if (!addAttachment) {
          Logger.warn("No addAttachment callback provided");
          return;
        }

        const fileDetails = await this.apiRequests
          .sendFileDetails({ path: data.path })
          .catch((error) => {
            toast({
              title: "Failed to get file details",
              description: error.message,
            });
            return null;
          });

        if (!fileDetails) {
          return;
        }

        const mimeType = fileDetails.mimeType || "text/plain";

        // Handle binary vs text files
        let blob: Blob;
        if (
          mimeType.startsWith("text/") ||
          mimeType.includes("json") ||
          mimeType.includes("xml")
        ) {
          // Text files - create blob directly from contents
          blob = new Blob([fileDetails.contents || ""], { type: mimeType });
        } else {
          // Binary files - use blob utility to decode base64
          if (fileDetails.contents) {
            try {
              // Create data URL using utility and deserialize blob
              const dataURL = base64ToDataURL(
                fileDetails.contents as Base64String,
                mimeType,
              );
              blob = deserializeBlob(dataURL);
            } catch {
              // Fallback to treating as text
              blob = new Blob([fileDetails.contents], { type: mimeType });
            }
          } else {
            blob = new Blob([""], { type: mimeType });
          }
        }

        const file = new File([blob], name, { type: mimeType });
        addAttachment(file);

        // Close completion and delete the entire mention text (from # to cursor)
        view.dispatch({
          changes: { from, to, insert: "" },
        });

        closeCompletion(view);
      },
      info: () => {
        const element = document.createElement("div");
        element.classList.add("flex", "flex-col", "gap-1", "p-2");

        const title = document.createElement("div");
        title.classList.add("font-bold");
        title.textContent = name;
        element.append(title);

        const path = document.createElement("div");
        path.classList.add("text-xs", "text-muted-foreground");
        path.textContent = data.path;
        element.append(path);
        return element;
      },
    };
  }

  formatContext(item: FileContextItem): string {
    const { data, name } = item;
    return contextToXml({
      type: this.contextType,
      data: {
        name: name,
        path: data.path,
        isDirectory: data.isDirectory,
      },
      details: data.isDirectory
        ? "Directory containing files and subdirectories"
        : "File",
    });
  }
}
