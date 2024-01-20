/* Copyright 2024 Marimo. All rights reserved. */
import { useState, useRef, useEffect } from "react";
import { useTimer } from "./useTimer";
import useEvent from "react-use-event-hook";
import { Logger } from "@/utils/Logger";

export type RecordingStatus = "recording" | "paused" | "stopped";

export function useAudioRecorder(opts: {
  onDone?: (blob: Blob) => void;
  options?: MediaRecorderOptions;
}) {
  const { onDone, options } = opts;

  const [recordingStatus, setRecordingStatus] =
    useState<RecordingStatus>("stopped");
  const mediaRecorder = useRef<MediaRecorder>();
  const [allowed, setAllowed] = useState<boolean>(true);
  const [recordingBlob, setRecordingBlob] = useState<Blob>();

  const timer = useTimer();

  const start: () => void = useEvent(() => {
    timer.clear();

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        const recorder = new MediaRecorder(stream, options);
        setRecordingStatus("recording");
        mediaRecorder.current = recorder;

        recorder.start();
        timer.start();

        recorder.addEventListener("dataavailable", (event) => {
          setRecordingBlob(event.data);
          onDone?.(event.data);
          recorder.stream.getTracks().forEach((t) => t.stop());
          mediaRecorder.current = undefined;
        });
      })
      .catch((error: DOMException) => {
        Logger.log(error);
        setAllowed(false);
      });
  });

  const stop: () => void = useEvent(() => {
    mediaRecorder.current?.stop();
    timer.stop();
    setRecordingStatus("stopped");
  });

  const pauseResume = useEvent(() => {
    setRecordingStatus((state) => {
      if (state === "recording") {
        mediaRecorder.current?.pause();
        timer.stop();
        return "paused";
      } else if (state === "paused") {
        mediaRecorder.current?.resume();
        timer.start();
        return "recording";
      } else {
        return state;
      }
    });
  });

  // Cleanup
  useEffect(() => {
    return () => {
      mediaRecorder.current?.stream.getTracks().forEach((t) => t.stop());
      mediaRecorder.current?.stop();
      timer.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    start,
    stop,
    pauseResume,
    allowed,
    recordingBlob,
    recordingStatus,
    recordingTime: timer.time,
    mediaRecorder,
  };
}
