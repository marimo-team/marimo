/* Copyright 2024 Marimo. All rights reserved. */
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { toast } from "@/components/ui/use-toast";
import { sendCopy } from "@/core/network/requests";
import { PathBuilder, Paths } from "@/utils/paths";

export function useCopyNotebook(filePath: string) {
  const { openPrompt, closeModal } = useImperativeModal();

  return () => {
    const pathBuilder = new PathBuilder("/");
    openPrompt({
      title: "Copy notebook",
      description: "Enter a new filename for the notebook copy.",
      defaultValue: `_${Paths.basename(filePath)}`,
      confirmText: "Copy notebook",
      spellCheck: false,
      onConfirm: (destination: string) => {
        sendCopy({
          source: filePath,
          destination: pathBuilder.join(Paths.dirname(filePath), destination),
        });
        closeModal();
        toast({
          title: "Notebook copied",
          description: "A copy of the notebook has been created.",
        });
      },
    });
  };
}
