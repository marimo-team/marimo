/* Copyright 2024 Marimo. All rights reserved. */

import { cva, type VariantProps } from "class-variance-authority";
import { useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/utils/cn";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";

export const ErrorBanner = ({
  error,
  className,
}: {
  error: Error | string;
  className?: string;
}) => {
  const [open, setOpen] = useState(false);

  if (!error) {
    return null;
  }
  Logger.error(error);

  const message = prettyError(error);

  return (
    <>
      <Banner
        kind="danger"
        className={className}
        clickable={true}
        onClick={() => setOpen(true)}
      >
        <span className="line-clamp-4">{message}</span>
      </Banner>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent className="max-w-[80%] max-h-[80%] overflow-hidden flex flex-col">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-error">Error</AlertDialogTitle>
          </AlertDialogHeader>
          <pre className="text-error text-sm p-2 font-mono overflow-auto whitespace-pre-wrap">
            {message}
          </pre>
          <AlertDialogFooter>
            <AlertDialogAction autoFocus={true} onClick={() => setOpen(false)}>
              Ok
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

const bannerStyle = cva(
  "text-sm p-2 border whitespace-pre-wrap overflow-hidden",
  {
    variants: {
      kind: {
        danger:
          "text-error border-[var(--red-6)] shadow-mdSolid shadow-error bg-[var(--red-1)]",
        info: "text-primary border-[var(--blue-6)] shadow-mdSolid shadow-accent bg-[var(--blue-1)]",
        warn: "border-[var(--yellow-6)] bg-[var(--yellow-2)] dark:bg-[var(--yellow-4)] text-[var(--yellow-11)] dark:text-[var(--yellow-12)]",
      },
      clickable: {
        true: "cursor-pointer",
      },
    },
    compoundVariants: [
      {
        clickable: true,
        kind: "danger",
        className: "hover:bg-[var(--red-3)]",
      },
      {
        clickable: true,
        kind: "info",
        className: "hover:bg-[var(--blue-3)]",
      },
      {
        clickable: true,
        kind: "warn",
        className: "hover:bg-[var(--yellow-3)]",
      },
    ],
    defaultVariants: {
      kind: "info",
    },
  },
);

export const Banner = ({
  kind,
  clickable,
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof bannerStyle>) => {
  return (
    <div className={cn(bannerStyle({ kind, clickable }), className)} {...rest}>
      {children}
    </div>
  );
};
