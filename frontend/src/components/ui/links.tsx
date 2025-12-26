/* Copyright 2026 Marimo. All rights reserved. */
export const ExternalLink = ({
  href,
  children,
}: {
  href:
    | `https://platform.openai.com/${string}`
    | `https://console.anthropic.com/${string}`
    | `https://aistudio.google.com/${string}`
    | `https://github.com/${string}`
    | `https://openrouter.ai/${string}`
    | `https://docs.marimo.io/${string}`
    | `https://docs.python.org/${string}`
    | `https://marimo.io/${string}`
    | `https://links.marimo.app/${string}`
    | `https://wandb.ai/${string}`
    | `https://portal.azure.com/${string}`;
  children: React.ReactNode;
}) => {
  return (
    <a href={href} target="_blank" className="text-link hover:underline">
      {children}
    </a>
  );
};
