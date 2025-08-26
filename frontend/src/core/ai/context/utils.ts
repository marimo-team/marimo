/* Copyright 2024 Marimo. All rights reserved. */

export interface AiContextPayload {
  type: string;
  data: Record<string, unknown>;
  details?: string;
}

// XML escaping utility
function escapeXml(unsafe: string): string {
  return (
    unsafe
      // We don't escape these characters because this is for an LLM and they can interpret this just fine.
      // .replaceAll("&", "&amp;")
      // .replaceAll('"', "&quot;")
      // .replaceAll("'", "&#39;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
  );
}

// Convert a single Context object to XML
export function contextToXml(context: AiContextPayload): string {
  const { type, data, details } = context;

  // Start with opening tag
  let xml = `<${type}`;

  // Add data as attributes
  for (const [key, value] of Object.entries(data)) {
    const escapedValue = escapeXml(String(value));
    if (value !== undefined) {
      xml += ` ${key}="${escapedValue}"`;
    }
  }

  // Close the opening tag
  xml += ">";

  // Add details as content if present
  if (details) {
    xml += escapeXml(details);
  }

  // Add closing tag
  xml += `</${type}>`;

  return xml;
}
