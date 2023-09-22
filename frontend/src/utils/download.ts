/* Copyright 2023 Marimo. All rights reserved. */
import { toPng } from "html-to-image";
import { toast } from "@/components/ui/use-toast";

export async function downloadHTMLAsImage(
  element: HTMLElement,
  filename: string
) {
  try {
    // Add classnames for printing
    document.body.classList.add("printing");
    // Get screenshot
    const dataUrl = await toPng(element);
    // Create an anchor element
    const a = document.createElement("a");
    // Create a PNG image from the canvas
    a.href = dataUrl;
    a.download = filename.endsWith(".png") ? filename : `${filename}.png`;
    // Download the image
    a.click();
  } catch {
    toast({
      title: "Error",
      description: "Failed to export as PNG.",
      variant: "danger",
    });
  } finally {
    // Remove classnames for printing
    document.body.classList.remove("printing");
  }
}
