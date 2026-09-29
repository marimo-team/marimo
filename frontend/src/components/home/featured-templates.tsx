/* Copyright 2026 Marimo. All rights reserved. */

import { ArrowRightIcon, PlusIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/use-toast";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Banner } from "@/plugins/impl/common/error-banner";
import { prettyError } from "@/utils/errors";
import { asURL } from "@/utils/url";
import { newNotebookURL } from "@/utils/urls";
import {
  launchTemplate,
  listTemplates,
  type TemplateCatalogResponse,
} from "./template-client";
import { TemplateBrowserDialog } from "./template-browser-dialog";
import { TemplateCard, type TemplateSummary } from "./template-card";

export const FeaturedTemplates = () => {
  const catalog = useAsyncData(listTemplates, []);
  const [isBrowserOpen, setIsBrowserOpen] = useState(false);
  const [launchingTemplateIds, setLaunchingTemplateIds] = useState(
    () => new Set<string>(),
  );

  const handleLaunch = async (template: TemplateSummary): Promise<boolean> => {
    const reservedTab = window.open("about:blank", "_blank");
    if (!reservedTab) {
      toast({
        title: "Could not open template",
        description: "Allow pop-ups for this site and try again.",
        variant: "danger",
      });
      return false;
    }
    reservedTab.opener = null;
    setLaunchingTemplateIds((ids) => new Set(ids).add(template.id));
    try {
      const fileKey = await launchTemplate(template.id);
      reservedTab.location.href = asURL(
        `?file=${encodeURIComponent(fileKey)}`,
      ).toString();
      return true;
    } catch (error) {
      reservedTab.close();
      toast({
        title: "Could not open template",
        description: prettyError(error),
        variant: "danger",
      });
      return false;
    } finally {
      setLaunchingTemplateIds((ids) => {
        const nextIds = new Set(ids);
        nextIds.delete(template.id);
        return nextIds;
      });
    }
  };

  const featured = getFeaturedTemplates(catalog.data);

  return (
    <section className="flex flex-col gap-3" aria-labelledby="templates-title">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 id="templates-title" className="text-xl font-semibold">
            What will you explore?
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Start from a working example and make it your own.
          </p>
        </div>
        <Button variant="outline" asChild={true}>
          <a href={newNotebookURL()} target="_blank" rel="noreferrer">
            <PlusIcon className="mr-2 h-4 w-4" />
            Blank notebook
          </a>
        </Button>
      </div>
      {catalog.isPending && <TemplateCardSkeletons />}
      {catalog.error && (
        <Banner
          kind="danger"
          className="flex items-center justify-between gap-4 rounded p-4"
        >
          <span>
            Templates are unavailable. You can still create a blank notebook.
          </span>
          <Button
            variant="outlineDestructive"
            size="xs"
            onClick={catalog.refetch}
          >
            Retry loading templates
          </Button>
        </Banner>
      )}
      {featured.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              isLaunching={launchingTemplateIds.has(template.id)}
              onLaunch={handleLaunch}
            />
          ))}
        </div>
      )}
      {catalog.data && (
        <div className="flex justify-end">
          <Button
            variant="link"
            size="sm"
            className="px-0"
            onClick={() => setIsBrowserOpen(true)}
          >
            Browse all templates
            <ArrowRightIcon className="ml-2 h-4 w-4" />
          </Button>
        </div>
      )}
      {catalog.data && (
        <TemplateBrowserDialog
          catalog={catalog.data}
          open={isBrowserOpen}
          onOpenChange={setIsBrowserOpen}
          launchingTemplateIds={launchingTemplateIds}
          onLaunch={handleLaunch}
        />
      )}
    </section>
  );
};

const getFeaturedTemplates = (
  catalog: TemplateCatalogResponse | undefined,
): TemplateSummary[] => {
  if (!catalog) {
    return [];
  }
  const templatesById = new Map(
    catalog.templates.map((template) => [template.id, template]),
  );
  return catalog.featuredIds.flatMap((id) => {
    const template = templatesById.get(id);
    return template ? [template] : [];
  });
};

const TemplateCardSkeletons = () => (
  <div
    className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
    aria-label="Loading templates"
  >
    {[0, 1, 2, 3, 4, 5].map((index) => (
      <Skeleton key={index} className="h-52 rounded-lg" />
    ))}
  </div>
);
