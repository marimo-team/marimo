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
import React, { type PropsWithChildren } from "react";
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
            <p className="my-2 prose">
              We want to hear from <span className="font-bold">you</span>: from
              minor bug reports to wishlist features and everything in between.
              Here are some ways you can get in touch:
            </p>
            <ul className="list-disc ml-8 my-2 prose">
              <li className="my-0">
                Take our{" "}
                <a
                  href={Constants.feedbackForm}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  two-minute survey.
                </a>
              </li>
              <li className="my-0">
                File a{" "}
                <a
                  href={Constants.issuesPage}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  GitHub issue.
                </a>
              </li>
              <li className="my-0">
                Chat with us on{" "}
                <a
                  href={Constants.discordLink}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  Discord.
                </a>
              </li>
            </ul>
            <p className="my-2 prose">
              We're excited you're here as we discover and build the future of
              Python data tooling together. Thanks for being part of our
              community!
            </p>
          </DialogDescription>
        </DialogHeader>
      </form>
    </DialogContent>
  );
};
