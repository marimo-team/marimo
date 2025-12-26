/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogDestructiveAction,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "./alert-dialog";

interface ConfirmationButtonProps {
  /**
   * The button element to trigger the confirmation dialog
   */
  children: React.ReactElement;
  /**
   * Title of the confirmation dialog
   */
  title: string;
  /**
   * Description/message of the confirmation dialog
   */
  description: string;
  /**
   * Callback when the user confirms the action
   */
  onConfirm: () => void;
  /**
   * Text for the confirm button (default: "Continue")
   */
  confirmText?: string;
  /**
   * Text for the cancel button (default: "Cancel")
   */
  cancelText?: string;
  /**
   * Whether to use destructive styling for the confirm button
   */
  destructive?: boolean;
}

export const ConfirmationButton: React.FC<ConfirmationButtonProps> = ({
  children,
  title,
  description,
  onConfirm,
  confirmText = "Continue",
  cancelText = "Cancel",
  destructive = false,
}) => {
  const [open, setOpen] = React.useState(false);

  const handleConfirm = () => {
    onConfirm();
    setOpen(false);
  };

  const ActionComponent = destructive
    ? AlertDialogDestructiveAction
    : AlertDialogAction;

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild={true}>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelText}</AlertDialogCancel>
          <ActionComponent onClick={handleConfirm}>
            {confirmText}
          </ActionComponent>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
