/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import React from "react";
import { Button } from "../ui/button";
import { CircleIcon, SquareIcon } from "lucide-react";
import { RecordingStatus } from "@/hooks/useAudioRecorder";

interface AudioRecorderProps {
  onStart: () => void;
  onStop: () => void;
  onPause: () => void;
  status: RecordingStatus;
  time?: string;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onStart,
  onStop,
  onPause,
  status,
  time,
}) => {
  return (
    <div className="flex items-center gap-3">
      {status === "stopped" && (
        <Button
          data-testid="audio-recorder-start"
          variant="secondary"
          onClick={onStart}
          className="w-[50px]"
        >
          <CircleIcon
            className={cn("w-6 h-6 border border-input rounded-full")}
            strokeWidth={1.5}
            fill="var(--red-9)"
          />
        </Button>
      )}
      {status === "recording" && (
        <Button
          data-testid="audio-recorder-pause"
          variant="secondary"
          onClick={onStop}
          className="w-[50px]"
        >
          <SquareIcon
            className="w-5 h-5 rounded-sm"
            fill="var(--red-9)"
            strokeWidth={1.5}
          />
          <CircleIcon
            className={cn("w-6 h-6 absolute opacity-20 animate-ping")}
            fill="var(--red-9)"
            style={{ animationDuration: "1.5s" }}
            strokeWidth={0}
          />
        </Button>
      )}
      {time && <span className="text-sm font-bold">{time}s</span>}
    </div>
  );
};
