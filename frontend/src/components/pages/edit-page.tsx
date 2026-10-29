/* Copyright 2026 Marimo. All rights reserved. */

import { useSetAtom, useStore } from "jotai";
import { notebookAtom } from "@/core/cells/cells";
import { notebookCells } from "@/core/cells/utils";
import type { AppConfig, UserConfig } from "@/core/config/config-schema";
import { KnownQueryParams } from "@/core/constants";
import { EditApp } from "@/core/edit-app";
import { getSessionId } from "@/core/kernel/session";
import { DocumentProvider } from "@/core/notebook/document";
import { lastSavedNotebookAtom } from "@/core/saving/state";
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
  const store = useStore();
  const setLastSavedNotebook = useSetAtom(lastSavedNotebookAtom);
  const { connection, reconnect, documentModel } = useNotebookSession({
    autoInstantiate: props.userConfig.runtime.auto_instantiate,
    onKernelReady: (layout) => {
      const cells = notebookCells(store.get(notebookAtom));
      const names = cells.map((cell) => cell.name);
      const codes = cells.map((cell) => cell.code);
      const configs = cells.map((cell) => cell.config);
      setLastSavedNotebook({ names, codes, configs, layout });
    },
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
