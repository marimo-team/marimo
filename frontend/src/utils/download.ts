/* Copyright 2024 Marimo. All rights reserved. */
import { toPng } from "html-to-image";
import { toast } from "@/components/ui/use-toast";

export async function downloadHTMLAsImage(
  element: HTMLElement,
  filename: string,
) {
  // Capture current scroll position
  const appEl = document.getElementById("App");
  const currentScrollY = appEl?.scrollTop ?? 0;
  // Add classnames for printing
  document.body.classList.add("printing");
  try {
    // Get screenshot
    const dataUrl = await toPng(element);
    downloadByURL(
      dataUrl,
      filename.endsWith(".png") ? filename : `${filename}.png`,
    );
  } catch {
    toast({
      title: "Error",
      description: "Failed to export as PNG.",
      variant: "danger",
    });
  } finally {
    // Remove classnames for printing
    document.body.classList.remove("printing");
    // Restore scroll position
    requestAnimationFrame(() => {
      appEl?.scrollTo(0, currentScrollY);
    });
  }
}

export function downloadByURL(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  a.remove();
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  downloadByURL(url, filename);
}
