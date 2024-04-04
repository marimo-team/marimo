/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { useDropzone } from "react-dropzone";
import { Upload, MousePointerSquareDashedIcon } from "lucide-react";

import { cn } from "@/utils/cn";
import { IPlugin, IPluginProps, Setter } from "../types";
import { filesToBase64 } from "../../utils/fileToBase64";
import { buttonVariants } from "../../components/ui/button";
import { renderHTML } from "../core/RenderHTML";
import { toast } from "@/components/ui/use-toast";

type FileUploadType = "button" | "area";

/**
 * Arguments for a file upload area/button
 *
 * @param filetypes - file types to accept (same as HTML input's accept attr)
 * @param multiple - whether to allow the user to upload multiple files
 * @param label - a label for the file upload area
 */
interface Data {
  filetypes: string[];
  multiple: boolean;
  kind: FileUploadType;
  label: string | null;
}

type T = Array<[string, string]>;

export class FileUploadPlugin implements IPlugin<T, Data> {
  tagName = "marimo-file";

  validator = z.object({
    filetypes: z.array(z.string()),
    multiple: z.boolean(),
    kind: z.enum(["button", "area"]),
    label: z.string().nullable(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <FileUpload
        label={props.data.label}
        filetypes={props.data.filetypes}
        multiple={props.data.multiple}
        kind={props.data.kind}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

/**
 * @param value - array of (filename, filecontents) tuples; filecontents should
 *                be b64 encoded.
 * @param setValue - communicate file upload
 */
interface FileUploadProps extends Data {
  value: T;
  setValue: Setter<T>;
}

function groupFileTypesByMIMEType(extensions: string[]) {
  const filesByMIMEType: Record<string, string[]> = {};

  const appendExt = (mimetype: string, extension: string) => {
    if (Object.hasOwnProperty.call(filesByMIMEType, mimetype)) {
      filesByMIMEType[mimetype].push(extension);
    } else {
      filesByMIMEType[mimetype] = [extension];
    }
  };

  extensions.forEach((extension) => {
    switch (extension) {
      case ".png":
      case ".jpg":
      case ".jpeg":
      case ".gif":
      case ".avif":
      case ".bmp":
      case ".ico":
      case ".svg":
      case ".tiff":
      case ".webp":
        appendExt("image/*", extension);
        break;
      case ".avi":
      case ".mp4":
      case ".mpeg":
      case ".ogg":
      case ".webm":
        appendExt("video/*", extension);
        break;
      case ".pdf":
        appendExt("application/pdf", extension);
        break;
      case ".csv":
        appendExt("text/csv", extension);
        break;
      default:
        appendExt("text/plain", extension);
    }
  });

  return filesByMIMEType;
}

// We may want to increase this based on user feedback
//
// But rather than forever increasing this, we should consider
// adding a non-browser file-chooser which allows users to select files from
// their local filesystem, and we only return the path.
//
// By using the browser's file chooser, it is more secure as we don
// not get access to the uploaded file's path but
// we are forced to upload the file to browser memory before
// sending it to the server.
const MAX_SIZE = 100_000_000; // 100 MB

/* TODO(akshayka): Allow uploading files one-by-one and removing uploaded files
 * when multiple is `True`*/
export const FileUpload = (props: FileUploadProps): JSX.Element => {
  const acceptGroups = groupFileTypesByMIMEType(props.filetypes);
  const { setValue, kind, multiple, value } = props;
  const { getRootProps, getInputProps, isFocused, isDragAccept, isDragReject } =
    useDropzone({
      accept: acceptGroups,
      multiple: multiple,
      maxSize: MAX_SIZE,
      onError: (error) => {
        console.error(error);
        toast({
          title: "File upload failed",
          description: error.message,
          variant: "danger",
        });
      },
      onDropRejected: (rejectedFiles) => {
        toast({
          title: "File upload failed",
          description: (
            <div className="flex flex-col gap-1">
              {rejectedFiles.map((file) => (
                <div key={file.file.name}>
                  {file.file.name} (
                  {file.errors.map((e) => e.message).join(", ")})
                </div>
              ))}
            </div>
          ),
          variant: "danger",
        });
      },
      onDrop: (acceptedFiles) => {
        filesToBase64(acceptedFiles)
          .then((value) => {
            setValue(value);
          })
          .catch((error) => {
            console.error(error);
            toast({
              title: "File upload failed",
              description: "Failed to convert file to base64.",
              variant: "danger",
            });
          });
      },
    });

  if (kind === "button") {
    // TODO(akshayka): React to a change in `value` due to an update from another
    // instance of this element. Browsers do not allow scripts to set the `value`
    // on a file input element.
    // One way to do this:
    // - hide the input element with a hidden attribute
    // - create a button and some text that reflects what has been uploaded;
    //   link button to the hidden input element
    const label = props.label ?? "Upload";
    return (
      <>
        <button
          data-testid="marimo-plugin-file-upload-button"
          {...getRootProps({})}
          className={buttonVariants({
            variant: "secondary",
            size: "xs",
          })}
        >
          {renderHTML({ html: label })}
          <Upload size={14} className="ml-2" />
        </button>
        <input {...getInputProps({})} type="file" />
      </>
    );
  }

  const uploadedFiles = value.map(([fileName, _]) => (
    <li key={fileName}>{fileName}</li>
  ));

  const uploaded = uploadedFiles.length > 0;
  const label =
    props.label ?? "Drag and drop files here, or click to open file browser";
  return (
    <section>
      <div
        className={cn(
          "mt-3 mb-2 w-full flex flex-col items-center justify-center ",
          "px-6 py-6 sm:px-8 sm:py-8 md:py-10 md:px-16",
          "border rounded-sm",
          "text-sm text-muted-foreground",
          "hover:cursor-pointer",
          "active:shadow-xsSolid",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:border-accent",
          !isFocused && "border-input/60 border-dashed",
          isFocused && "border-solid",
        )}
        {...getRootProps()}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center justify-center flex-grow gap-3">
          {uploaded ? (
            <span>To re-upload: {renderHTML({ html: label })}</span>
          ) : (
            <span className="mt-0">{renderHTML({ html: label })}</span>
          )}
          <div className="flex flex-row items-center justify-center flex-grow gap-3 hover:text-primary">
            <Upload
              strokeWidth={1.4}
              className={cn(
                isDragAccept && "text-primary",
                isDragReject && "text-destructive",
              )}
            />
            <MousePointerSquareDashedIcon
              strokeWidth={1.4}
              className={cn(
                isDragAccept && "text-primary",
                isDragReject && "text-destructive",
              )}
            />
          </div>
        </div>
      </div>

      <aside>
        {uploaded ? (
          <span className="markdown">
            <strong>Uploaded files</strong>
            <ul style={{ margin: 0 }}>{uploadedFiles}</ul>
          </span>
        ) : null}
      </aside>
    </section>
  );
};
