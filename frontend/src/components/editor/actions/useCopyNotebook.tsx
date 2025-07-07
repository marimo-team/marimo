/* Copyright 2024 Marimo. All rights reserved. */
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { toast } from "@/components/ui/use-toast";
import { sendCopy } from "@/core/network/requests";
import { openNotebook } from "@/utils/links";
import { PathBuilder, Paths } from "@/utils/paths";

export function useCopyNotebook(source: string | null) {
  const { openPrompt, closeModal } = useImperativeModal();

  return () => {
    if (!source) {
      return null;
    }
    const pathBuilder = PathBuilder.guessDeliminator(source);
    const filename = Paths.basename(source);

    openPrompt({
      title: "Copy notebook",
      description: "Enter a new filename for the notebook copy.",
      defaultValue: `_${filename}`,
      confirmText: "Copy notebook",
      spellCheck: false,
      onConfirm: (filename: string) => {
        const destination = pathBuilder.join(Paths.dirname(source), filename);
        sendCopy({
          source: source,
          destination: destination,
        }).then(() => {
          closeModal();
          toast({
            title: "Notebook copied",
            description: "A copy of the notebook has been created.",
          });
          openNotebook(destination);
        });
      },
    });
  };
}
