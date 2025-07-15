/* Copyright 2024 Marimo. All rights reserved. */

import { AlertCircleIcon, RotateCcwIcon, XIcon } from "lucide-react";
import type React from "react";
import type { AppConfig } from "@/core/config/config-schema";
import { useBanners, useBannersActions } from "@/core/errors/state";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { Banner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { Button } from "../ui/button";
import { useRestartKernel } from "./actions/useRestartKernel";

interface Props {
  width: AppConfig["width"];
}

export const NotebookBanner: React.FC<Props> = ({ width }) => {
  const { banners } = useBanners();
  const { removeBanner } = useBannersActions();

  if (banners.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-4 mb-5 print:hidden",
        width === "columns" && "sticky left-12 w-full max-w-[80vw]",
      )}
    >
      {banners.map((banner) => (
        <Banner
          kind={banner.variant || "info"}
          key={banner.id}
          className="flex flex-col rounded p-3"
        >
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              <AlertCircleIcon className="w-5 h-5 inline-block mr-2" />
              {banner.title}
            </span>
            <Button
              data-testid="remove-banner-button"
              variant="text"
              size="icon"
              onClick={() => removeBanner(banner.id)}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div className="flex justify-between items-end">
            <span>{renderHTML({ html: banner.description })}</span>
            {banner.action === "restart" && <RestartSessionButton />}
          </div>
        </Banner>
      ))}
    </div>
  );
};

const RestartSessionButton = () => {
  const restartKernel = useRestartKernel();
  return (
    <Button
      data-testid="restart-session-button"
      variant="link"
      size="xs"
      onClick={restartKernel}
    >
      <RotateCcwIcon className="w-3 h-3 mr-2" />
      Restart
    </Button>
  );
};
