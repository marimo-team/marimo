/* Copyright 2026 Marimo. All rights reserved. */
import { Provider } from "jotai";
import { type PropsWithChildren, useState } from "react";
import {
  type FallbackProps,
  ErrorBoundary as ReactErrorBoundary,
} from "react-error-boundary";
import { store } from "@/core/state/jotai";
import { Button } from "../../ui/button";
import { Dialog, DialogTrigger } from "../../ui/dialog";
import { TooltipProvider } from "../../ui/tooltip";
import { FeedbackModal } from "../chrome/components/feedback-button";

export const ErrorBoundary: React.FC<PropsWithChildren> = (props) => {
  return (
    <ReactErrorBoundary FallbackComponent={FallbackComponent}>
      {props.children}
    </ReactErrorBoundary>
  );
};

const FallbackComponent: React.FC<FallbackProps> = (props) => {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex-1 flex items-center justify-center flex-col space-y-4 max-w-2xl mx-auto px-6 pb-6">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <pre className="text-xs bg-muted/40 border rounded-md p-4 max-w-[80%] whitespace-normal">
        {props.error?.message}
      </pre>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild={true}>
            <Button variant="outline">Report an issue</Button>
          </DialogTrigger>
          {open && (
            <Provider store={store}>
              <TooltipProvider>
                <FeedbackModal onClose={() => setOpen(false)} />
              </TooltipProvider>
            </Provider>
          )}
        </Dialog>
        <Button
          data-testid="reset-error-boundary-button"
          onClick={props.resetErrorBoundary}
          variant="outline"
        >
          Try again
        </Button>
      </div>
    </div>
  );
};
