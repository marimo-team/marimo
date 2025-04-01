/* Copyright 2024 Marimo. All rights reserved. */
export const ExternalLink = ({
  href,
  children,
}: { href: string; children: React.ReactNode }) => {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-link hover:underline"
    >
      {children}
    </a>
  );
};
