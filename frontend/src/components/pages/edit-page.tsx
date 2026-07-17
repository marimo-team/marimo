/* Copyright 2026 Marimo. All rights reserved. */

import { lazy } from "react";
import type { AppConfig, UserConfig } from "@/core/config/config-schema";
import { hasQueryParam, KnownQueryParams } from "@/core/constants";
import { EditApp } from "@/core/edit-app";
import { AppChrome } from "../editor/chrome/wrapper/app-chrome";

const LazyCommandPalette = lazy(
  () => import("../editor/controls/command-palette"),
);

interface Props {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

const hideChrome =
  new URL(window.location.href).searchParams.get(
    KnownQueryParams.showChrome,
  ) === "false" || hasQueryParam(KnownQueryParams.printPdf);

const EditPage = (props: Props) => {
  if (hideChrome) {
    return (
      <>
        <EditApp hideControls={true} {...props} />
        <LazyCommandPalette />
      </>
    );
  }

  return (
    <AppChrome>
      <EditApp {...props} />
      <LazyCommandPalette />
    </AppChrome>
  );
};

export default EditPage;
