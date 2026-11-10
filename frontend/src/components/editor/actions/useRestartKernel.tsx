/* Copyright 2026 Marimo. All rights reserved. */

import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { useRequestClient } from "@/core/network/requests";
import { reloadSafe } from "@/utils/reload-safe";

export function useRestartKernel() {
  const { openConfirm } = useImperativeModal();
  const { sendRestart } = useRequestClient();

  return () => {
    openConfirm({
      title: "Restart Kernel",
      description:
        "This will restart the Python kernel. You'll lose all data that's in memory. You will also lose any unsaved changes, so make sure to save your work before restarting.",
      variant: "destructive",
      confirmAction: (
        <AlertDialogDestructiveAction
          onClick={async () => {
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
