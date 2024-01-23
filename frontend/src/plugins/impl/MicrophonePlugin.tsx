/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";
import { Labeled } from "./common/labeled";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { AudioRecorder } from "@/components/audio/audio-recorder";
import { blobToBase64 } from "@/utils/fileToBase64";

/**
 * Base64 encoded audio file.
 */
type Value = string;

interface Data {
  label?: string | null;
}

export class MicrophonePlugin implements IPlugin<Value, Data> {
  tagName = "marimo-microphone";

  validator = z.object({
    label: z.string().nullish(),
  });

  render(props: IPluginProps<Value, Data>): JSX.Element {
    return <Microphone {...props} />;
  }
}

const Microphone = ({ setValue, data }: IPluginProps<Value, Data>) => {
  const { start, stop, pauseResume, recordingStatus, recordingTime, allowed } =
    useAudioRecorder({
      onDone: async (file) => {
        const base64 = await blobToBase64(file);
        setValue(base64);
      },
    });

  return (
    <Labeled label={data.label} align="top">
      {!allowed && (
        <div className="text-destructive text-sm">
          Microphone access is disabled. Please allow microphone access in your
          browser.
        </div>
      )}
      <AudioRecorder
        onStart={start}
        onStop={stop}
        onPause={pauseResume}
        status={recordingStatus}
        time={recordingTime}
      />
    </Labeled>
  );
};
