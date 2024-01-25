/* Copyright 2023 Marimo. All rights reserved. */
import { bannerAtom } from "@/core/errors/state";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { Banner } from "@/plugins/impl/common/error-banner";
import { useAtom } from "jotai";
import { AlertCircleIcon, XIcon } from "lucide-react";
import React from "react";
import { Button } from "../ui/button";

export const NotebookBanner: React.FC = (props) => {
  const [banner, setBanner] = useAtom(bannerAtom);

  if (!banner) {
    return null;
  }

  return (
    <Banner kind={banner.variant} className="mb-10 flex flex-col rounded p-3">
      <div className="flex justify-between">
        <span className="font-bold text-lg flex items-center mb-2">
          <AlertCircleIcon className="w-5 h-5 inline-block mr-2" />
          {banner.title}
        </span>
        <Button variant="text" size="icon" onClick={() => setBanner(undefined)}>
          <XIcon className="w-5 h-5" />
        </Button>
      </div>
      <span>{renderHTML({ html: banner.description })}</span>
    </Banner>
  );
};
