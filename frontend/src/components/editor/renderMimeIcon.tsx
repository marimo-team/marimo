/* Copyright 2024 Marimo. All rights reserved. */
export function renderMimeIcon(mime: string) {
  switch (mime) {
    case "text/html":
      return "🌐";
    case "text/plain":
      return "📄";
    case "application/json":
      return "📦";
    case "image/png":
    case "image/tiff":
    case "image/avif":
    case "image/bmp":
    case "image/gif":
    case "image/jpeg":
      return "🖼️";
    case "image/svg+xml":
      return "🎨";
    case "video/mp4":
    case "video/mpeg":
      return "🎥";
    case "application/vnd.marimo+error":
      return "🚨";
    case "application/vnd.marimo+traceback":
      return "🐍";
    case "text/csv":
      return "📊";
    case "text/markdown":
      return "📝";
    case "application/vnd.vegalite.v5+json":
    case "application/vnd.vega.v5+json":
      return "📊";
    case "application/vnd.marimo+mimebundle":
      return "📦";
    default:
      return "❓";
  }
}
