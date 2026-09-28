/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { ExternalLinkIcon, LayoutTemplateIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "@/components/ui/use-toast";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Banner } from "@/plugins/impl/common/error-banner";
import { prettyError } from "@/utils/errors";
import { asURL } from "@/utils/url";
import { Header } from "./components";
import { launchTemplate, listTemplates } from "./template-client";

type TemplateSummary = components["schemas"]["TemplateSummary"];

export const FeaturedTemplates = () => {
  const catalog = useAsyncData(listTemplates, []);

  if (catalog.error) {
    return (
      <Banner kind="danger" className="rounded p-4">
        Templates are unavailable. You can still create a blank notebook.
      </Banner>
    );
  }

  if (!catalog.data) {
    return null;
  }

  const templatesById = new Map(
    catalog.data.templates.map((template) => [template.id, template]),
  );
  const featured = catalog.data.featuredIds.flatMap((id) => {
    const template = templatesById.get(id);
    return template ? [template] : [];
  });

  if (featured.length === 0) {
    return null;
  }

  return (
    <section className="flex flex-col gap-2" aria-labelledby="templates-title">
      <Header Icon={LayoutTemplateIcon}>
        <span id="templates-title">Start with a template</span>
      </Header>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {featured.map((template) => (
          <FeaturedTemplateCard key={template.id} template={template} />
        ))}
      </div>
    </section>
  );
};

const FeaturedTemplateCard = ({ template }: { template: TemplateSummary }) => {
  const [isLaunching, setIsLaunching] = useState(false);

  const handleLaunch = async () => {
    const reservedTab = window.open("about:blank", "_blank");
    if (!reservedTab) {
      toast({
        title: "Could not open template",
        description: "Allow pop-ups for this site and try again.",
        variant: "danger",
      });
      return;
    }
    reservedTab.opener = null;
    setIsLaunching(true);
    try {
      const fileKey = await launchTemplate(template.id);
      reservedTab.location.href = asURL(
        `?file=${encodeURIComponent(fileKey)}`,
      ).toString();
    } catch (error) {
      reservedTab.close();
      toast({
        title: "Could not open template",
        description: prettyError(error),
        variant: "danger",
      });
    } finally {
      setIsLaunching(false);
    }
  };

  return (
    <button
      type="button"
      aria-label={`Use template: ${template.title}`}
      data-testid={`template-card-${template.id}`}
      disabled={isLaunching}
      onClick={handleLaunch}
      className="group overflow-hidden rounded-lg border bg-background text-left shadow-xs transition-colors hover:bg-accent/20 disabled:cursor-wait disabled:opacity-70"
    >
      <img
        src={template.previewUrl}
        alt=""
        className="h-28 w-full border-b bg-(--slate-2) object-cover"
      />
      <div className="relative flex min-h-24 flex-col gap-1 p-4 pr-10">
        <h3 className="font-medium text-foreground">{template.title}</h3>
        <p className="text-sm text-muted-foreground">
          {isLaunching ? "Opening template…" : template.description}
        </p>
        <ExternalLinkIcon className="absolute right-4 top-4 h-5 w-5 text-primary opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
    </button>
  );
};
