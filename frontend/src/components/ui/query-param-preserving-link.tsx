/* Copyright 2026 Marimo. All rights reserved. */

import React, { useRef } from "react";
import { usePress } from "react-aria";

interface QueryParamPreservingLinkProps
  extends Omit<React.HTMLAttributes<HTMLAnchorElement>, "href"> {
  href: string;
  children: React.ReactNode;
}

export const QueryParamPreservingLink: React.FC<
  QueryParamPreservingLinkProps
> = ({ href, children, ...props }) => {
  const ref = useRef<HTMLAnchorElement>(null);

  const navigateWithQueryParams = () => {
    const currentUrl = new URL(globalThis.location.href);
    // Preserve existing query parameters and update the hash
    currentUrl.hash = href;
    globalThis.history.pushState({}, "", currentUrl.toString());

    //manually dispatch hashchange event
    globalThis.dispatchEvent(new HashChangeEvent("hashchange"));

    // Scroll to the anchor
    const targetId = href.slice(1);
    const targetElement = document.getElementById(targetId);
    if (targetElement) {
      targetElement.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const { pressProps } = usePress({
    onPress: () => {
      navigateWithQueryParams();
    },
  });

  // For anchor links, we need to prevent default navigation
  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    navigateWithQueryParams();
  };

  return (
    <a ref={ref} href={href} {...pressProps} onClick={handleClick} {...props}>
      {children}
    </a>
  );
};
