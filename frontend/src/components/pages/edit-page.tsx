/* Copyright 2024 Marimo. All rights reserved. */

import type { AppConfig, UserConfig } from "@/core/config/config-schema";
import { KnownQueryParams } from "@/core/constants";
import { EditApp } from "@/core/edit-app";
import { AppChrome } from "../editor/chrome/wrapper/app-chrome";
import { CommandPalette } from "../editor/controls/command-palette";

interface Props {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

const hideChrome = (() => {
  const url = new URL(window.location.href);
  return url.searchParams.get(KnownQueryParams.showChrome) === "false";
})();

const EditPage = (props: Props) => {
  if (hideChrome) {
    return (
      <>
        <EditApp hideControls={true} {...props} />
        <CommandPalette />
      </>
    );
  }

  return (
    <AppChrome>
      <EditApp {...props} />
      <CommandPalette />
    </AppChrome>
  );
};

export default EditPage;
