/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import useEvent from "react-use-event-hook";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Paths } from "@/utils/paths";
import { updateQueryParams } from "@/utils/urls";
import { getAppConfig } from "../config/config";
import { KnownQueryParams } from "../constants";
import { connectionAtom } from "../network/connection";
import { sendRename } from "../network/requests";
import { WebSocketState } from "../websocket/types";
import { filenameAtom } from "./file-state";

export function useFilename() {
  return useAtomValue(filenameAtom);
}

export function useUpdateFilename() {
  const [connection] = useAtom(connectionAtom);
  const setFilename = useSetAtom(filenameAtom);
  const { openAlert } = useImperativeModal();

  const handleFilenameChange = useEvent(async (name: string) => {
    const appConfig = getAppConfig();
    if (connection.state !== WebSocketState.OPEN) {
      openAlert("Failed to save notebook: not connected to a kernel.");
      return null;
    }

    updateQueryParams((params) => {
      if (name === null) {
        params.delete(KnownQueryParams.filePath);
      } else {
        params.set(KnownQueryParams.filePath, name);
      }
    });

    return sendRename({ filename: name })
      .then(() => {
        setFilename(name);
        // Set document title: app_title takes precedence, then filename, then default
        document.title =
          appConfig.app_title || Paths.basename(name) || "Untitled Notebook";
        return name;
      })
      .catch((error) => {
        openAlert(error.message);
        return null;
      });
  });

  return handleFilenameChange;
}
