/* Copyright 2026 Marimo. All rights reserved. */

import type { AppConfig, UserConfig } from "@/core/config/config-schema";
import { KnownQueryParams } from "@/core/constants";
import { EditApp } from "@/core/edit-app";
import { getSessionId } from "@/core/kernel/session";
import { DocumentProvider } from "@/core/notebook/document";
import { useNotebookSession } from "@/core/session/useNotebookSession";
import { AppChrome } from "../editor/chrome/wrapper/app-chrome";

interface Props {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

const hideChrome = (() => {
  const url = new URL(window.location.href);
  return url.searchParams.get(KnownQueryParams.showChrome) === "false";
})();

/** Own the notebook session and provide its document model to the editor and its chrome. */
const EditPage = (props: Props) => {
  const { connection, reconnect, documentModel } = useNotebookSession({
    autoInstantiate: props.userConfig.runtime.auto_instantiate,
    sessionId: getSessionId(),
  });
  const app = (
    <EditApp
      {...props}
      hideControls={hideChrome}
      connection={connection}
      reconnect={reconnect}
    />
  );

  return (
    <DocumentProvider model={documentModel}>
      {hideChrome ? app : <AppChrome>{app}</AppChrome>}
    </DocumentProvider>
  );
};

export default EditPage;
