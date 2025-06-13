/* Copyright 2024 Marimo. All rights reserved. */

import { useSetAtom } from "jotai";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { connectionAtom } from "@/core/network/connection";
import { sendRestart } from "@/core/network/requests";
import { WebSocketState } from "@/core/websocket/types";
import { reloadSafe } from "@/utils/reload-safe";

export function useRestartKernel() {
  const { openConfirm } = useImperativeModal();
  const setConnection = useSetAtom(connectionAtom);

  return () => {
    openConfirm({
      title: "Restart Kernel",
      description:
        "This will restart the Python kernel. You'll lose all data that's in memory. You will also lose any unsaved changes, so make sure to save your work before restarting.",
      variant: "destructive",
      confirmAction: (
        <AlertDialogDestructiveAction
          onClick={async () => {
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
