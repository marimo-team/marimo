/* Copyright 2026 Marimo. All rights reserved. */
import type { ComponentPropsWithoutRef, ReactElement, ReactNode } from "react";
import { useRef } from "react";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/utils/cn";
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "./toast";

export const Toaster = () => {
  const { toasts } = useToast();

  return (
    <ToastProvider>
      {toasts.map(({ id, title, description, action, variant, ...props }) => (
        <ToastItem
          key={id}
          toastTitle={title}
          toastDescription={description}
          action={action}
          variant={variant}
          {...props}
        />
      ))}
      <ToastViewport />
    </ToastProvider>
  );
};

type ToastItemProps = Omit<
  ComponentPropsWithoutRef<typeof Toast>,
  "title" | "children"
> & {
  toastTitle?: ReactNode;
  toastDescription?: ReactNode;
  action?: ReactElement;
};

const ToastItem = ({
  toastTitle,
  toastDescription,
  action,
  variant,
  ...props
}: ToastItemProps) => {
  const descriptionRef = useRef<HTMLDivElement>(null);
  // Show copy button for danger toasts without action, typically used for errors.
  const showCopy = Boolean(toastDescription) && !action && variant === "danger";

  return (
    <Toast variant={variant} {...props}>
      <div className="grid min-w-0 flex-1 gap-1">
        {toastTitle && <ToastTitle>{toastTitle}</ToastTitle>}
        {toastDescription && (
          <ToastDescription ref={descriptionRef}>
            {toastDescription}
          </ToastDescription>
        )}
      </div>
      {action}
      {showCopy && (
        <CopyClipboardIcon
          tooltip="Copy error"
          ariaLabel="Copy error"
          className="h-4 w-4"
          buttonClassName={cn(
            "absolute right-8 top-2 rounded-md p-1 text-foreground/50 opacity-0 transition-opacity",
            "hover:text-foreground focus:opacity-100 focus:outline-hidden group-hover:opacity-100",
            "group-[.destructive]:text-red-300 hover:group-[.destructive]:text-red-500 focus:group-[.destructive]:ring-red-400 focus:group-[.destructive]:ring-offset-red-600",
          )}
          value={() =>
            descriptionRef.current?.innerText ??
            (typeof toastDescription === "string" ? toastDescription : "")
          }
        />
      )}
      <ToastClose />
    </Toast>
  );
};
