/* Copyright 2024 Marimo. All rights reserved. */
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { sendRestart } from "@/core/network/requests";

export function useRestartKernel() {
  const { openConfirm } = useImperativeModal();

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
            window.location.reload();
          }}
          aria-label="Confirm Restart"
        >
          Restart
        </AlertDialogDestructiveAction>
      ),
    });
  };
}
