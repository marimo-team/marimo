/* Copyright 2024 Marimo. All rights reserved. */
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { toast } from "@/components/ui/use-toast";
import { sendCopy } from "@/core/network/requests";
import { PathBuilder, Paths } from "@/utils/paths";

export function useCopyNotebook(source: string | null) {
  const { openPrompt, closeModal } = useImperativeModal();

  return () => {
    if (!source) {
      return null;
    }
    const pathBuilder = new PathBuilder("/");
    const filename = Paths.basename(source);

    openPrompt({
      title: "Copy notebook",
      description: "Enter a new filename for the notebook copy.",
      defaultValue: `_${filename}`,
      confirmText: "Copy notebook",
      spellCheck: false,
      onConfirm: (destination: string) => {
        sendCopy({
          source: source,
          destination: pathBuilder.join(Paths.dirname(source), destination),
        })
          .then(() => {
            closeModal();
            toast({
              title: "Notebook copied",
              description: "A copy of the notebook has been created.",
            });
            const notebookCopy = window.location.href.replace(
              filename,
              destination,
            );
            window.open(notebookCopy);
          })
          .catch((error) => {
            toast({
              title: "Failed to copy notebook",
              description: error.detail,
              variant: "danger",
            });
          });
      },
    });
  };
}
