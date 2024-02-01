/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import { Dialog } from "../ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";

interface ModalContextType {
  modal: React.ReactNode | null;
  setModal: (modal: React.ReactNode | null) => void;
}

const ModalContext = React.createContext<ModalContextType>({
  modal: null,
  setModal: () => {
    return;
  },
});

export const ModalProvider: React.FC<PropsWithChildren<{}>> = (props) => {
  const [modal, setModal] = React.useState<React.ReactNode | null>(null);

  return (
    <ModalContext.Provider value={{ modal, setModal }}>
      {modal}
      {props.children}
    </ModalContext.Provider>
  );
};
/**
 * This hook allows you to open and close the modal imperatively.
 *
 * @example
 * ```tsx
 * const { openModal, closeModal } = useImperativeModal();
 *
 * const handleOpenModal = () => {
 *  openModal(<DialogContent>...<Button onClick={closeModal}/>Cancel</DialogContent>);
 * }
 * ```
 */
export function useImperativeModal() {
  const context = React.useContext(ModalContext);

  if (context === undefined) {
    throw new Error("useModal must be used within a ModalProvider");
  }

  const closeModal = () => {
    context.setModal(null);
  };

  return {
    openModal: (content: React.ReactNode) => {
      context.setModal(
        <Dialog
          open={true}
          onOpenChange={(open) => {
            if (!open) {
              closeModal();
            }
          }}
        >
          {content}
        </Dialog>,
      );
    },
    openAlert: (content: React.ReactNode) => {
      context.setModal(
        <AlertDialog
          open={true}
          onOpenChange={(open) => {
            if (!open) {
              closeModal();
            }
          }}
        >
          <AlertDialogContent>
            {content}
            <AlertDialogFooter>
              <AlertDialogAction autoFocus={true} onClick={closeModal}>
                Ok
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>,
      );
    },
    openConfirm: (opts: {
      title: React.ReactNode;
      description?: React.ReactNode;
      confirmAction: React.ReactNode;
      variant?: "destructive";
    }) => {
      context.setModal(
        <AlertDialog
          open={true}
          onOpenChange={(open) => {
            if (!open) {
              closeModal();
            }
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle
                className={
                  opts.variant === "destructive" ? "text-destructive" : ""
                }
              >
                {opts.title}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {opts.description}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={closeModal}>Cancel</AlertDialogCancel>
              {opts.confirmAction}
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>,
      );
    },
    closeModal: closeModal,
  };
}
