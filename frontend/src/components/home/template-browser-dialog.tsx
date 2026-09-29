/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SearchInput } from "@/components/ui/input";
import type { TemplateCatalogResponse } from "./template-client";
import { TemplateCard, type TemplateSummary } from "./template-card";

type TemplateCategory = components["schemas"]["TemplateCategory"];

interface Props {
  catalog: TemplateCatalogResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  launchingTemplateIds: ReadonlySet<string>;
  onLaunch: (template: TemplateSummary) => Promise<boolean>;
}

export const TemplateBrowserDialog = ({
  catalog,
  open,
  onOpenChange,
  launchingTemplateIds,
  onLaunch,
}: Props) => {
  const [query, setQuery] = useState("");
  const groups = useMemo(
    () => groupTemplates(catalog, query),
    [catalog, query],
  );

  const handleOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
    if (!nextOpen) {
      setQuery("");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="w-[calc(100vw-2rem)] max-h-[90vh] overflow-hidden gap-0 p-0 sm:max-w-5xl sm:top-[5vh]">
        <DialogHeader className="p-6 pb-4 pr-12">
          <DialogTitle>Browse templates</DialogTitle>
          <DialogDescription>
            Choose a starting point and make it your own.
          </DialogDescription>
        </DialogHeader>
        <SearchInput
          aria-label="Search templates"
          placeholder="Search templates..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          rootClassName="border-y px-5 py-1"
        />
        <div className="min-h-48 overflow-y-auto p-6">
          {groups.length === 0 ? (
            <div className="flex min-h-36 items-center justify-center text-sm text-muted-foreground">
              No templates match “{query}”.
            </div>
          ) : (
            <div className="flex flex-col gap-8">
              {groups.map(({ category, templates }) => (
                <section
                  key={category.id}
                  aria-labelledby={`template-category-${category.id}`}
                  className="flex flex-col gap-3"
                >
                  <div>
                    <h3
                      id={`template-category-${category.id}`}
                      className="font-semibold"
                    >
                      {category.title}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {category.description}
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {templates.map((template) => (
                      <TemplateCard
                        key={template.id}
                        template={template}
                        isLaunching={launchingTemplateIds.has(template.id)}
                        onLaunch={onLaunch}
                        onLaunched={() => handleOpenChange(false)}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

function groupTemplates(catalog: TemplateCatalogResponse, query: string) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matches = (template: TemplateSummary) =>
    normalizedQuery.length === 0 ||
    template.title.toLocaleLowerCase().includes(normalizedQuery) ||
    template.description.toLocaleLowerCase().includes(normalizedQuery);

  return catalog.categories.flatMap((category: TemplateCategory) => {
    const templates = catalog.templates.filter(
      (template) =>
        template.categoryIds.includes(category.id) && matches(template),
    );
    return templates.length > 0 ? [{ category, templates }] : [];
  });
}
