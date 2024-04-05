/* Copyright 2024 Marimo. All rights reserved. */
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  DialogFooter,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Slot } from "@radix-ui/react-slot";
import React, { PropsWithChildren } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/use-toast";
import { Constants } from "@/core/constants";

export const FeedbackButton: React.FC<PropsWithChildren> = ({ children }) => {
  const { openModal, closeModal } = useImperativeModal();

  return (
    <Slot onClick={() => openModal(<FeedbackModal onClose={closeModal} />)}>
      {children}
    </Slot>
  );
};

const EmojiToRating: Record<string, number> = {
  "😡": 1,
  "🙁": 2,
  "😐": 3,
  "🙂": 4,
  "😍": 5,
};

const FeedbackModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  return (
    <DialogContent className="w-fit">
      <form
        onSubmit={async (e) => {
          e.preventDefault();

          const formData = new FormData(e.target as HTMLFormElement);
          const rating = formData.get("rating");
          const message = formData.get("message");

          // Fire-and-forget we don't care about the response
          void fetch("https://marimo.io/api/feedback", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              rating: rating,
              message,
            }),
          });
          onClose();
          toast({
            title: "Feedback sent!",
            description: "Thank you for your feedback!",
          });
        }}
      >
        <DialogHeader>
          <DialogTitle>Send Feedback</DialogTitle>
          <DialogDescription>
            Let us know what you think about marimo! If you have a bug that you
            would like to report, please use the{" "}
            <a
              href={Constants.issuesPage}
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              GitHub issue tracker
            </a>
            .
          </DialogDescription>
          <DialogDescription>
            Your feedback is anonymous and will help us improve marimo. Thank
            you!
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-6 py-4">
          <div className="flex gap-5 justify-center">
            {Object.entries(EmojiToRating).map(([emoji, rating]) => (
              <label
                key={emoji}
                className="flex flex-col items-center select-none"
              >
                <input
                  key={emoji}
                  type="radio"
                  className="peer hidden"
                  name="rating"
                  value={rating}
                  aria-label={emoji}
                />
                <span className="text-4xl peer-checked:opacity-100 opacity-40 cursor-pointer">
                  {emoji}
                </span>
              </label>
            ))}
          </div>
          <Textarea
            id="message"
            name="message"
            autoFocus={true}
            placeholder="Your feedback"
            rows={5}
            required={true}
            autoComplete="off"
          />
        </div>
        <DialogFooter>
          <Button
            data-testid="feedback-cancel-button"
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            data-testid="feedback-send-button"
            aria-label="Save"
            variant="default"
            type="submit"
          >
            Send
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
};
