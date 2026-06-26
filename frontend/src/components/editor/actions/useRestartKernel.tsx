/* Copyright 2026 Marimo. All rights reserved. */

import { useSetAtom } from "jotai";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { connectionAtom } from "@/core/network/connection";
import { useRequestClient } from "@/core/network/requests";
import { useSaveNotebook } from "@/core/saving/save-component";
import { WebSocketState } from "@/core/websocket/types";
import { Logger } from "@/utils/Logger";
import { reloadSafe } from "@/utils/reload-safe";

export function useRestartKernel() {
  const { openConfirm } = useImperativeModal();
  const setConnection = useSetAtom(connectionAtom);
  const { sendRestart } = useRequestClient();
  const { saveIfNotebookIsPersistent } = useSaveNotebook();

  return () => {
    openConfirm({
      title: "Restart Kernel",
      description:
        "This will restart the Python kernel. You'll lose all data that's in memory. Unsaved code changes are saved automatically before restarting.",
      variant: "destructive",
      confirmAction: (
        <AlertDialogDestructiveAction
          onClick={async () => {
            try {
              await saveIfNotebookIsPersistent();
            } catch (error) {
              Logger.warn("restart: pre-restart save failed", error);
            }
            setConnection({ state: WebSocketState.CLOSING });
            await sendRestart();
            reloadSafe();
          }}
          aria-label="Confirm Restart"
        >
          Restart
        </AlertDialogDestructiveAction>
      ),
    });
  };
}
