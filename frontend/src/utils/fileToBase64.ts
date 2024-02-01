/* Copyright 2024 Marimo. All rights reserved. */
export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.readAsDataURL(blob);
    reader.onload = (e) => {
      if (e.target?.result) {
        const dataURL = e.target.result as string;
        // Get contents from a string of the form: data:*/*;base64,contents
        const b64EncodedContents = dataURL.slice(dataURL.indexOf(",") + 1);
        resolve(b64EncodedContents);
      }
    };
  });
}

/**
 * Read contents of files as base64-encoded strings
 *
 * Returns a promised array of tuples [file name, file contents].
 */
export function filesToBase64(files: File[]): Promise<Array<[string, string]>> {
  return Promise.all(
    files.map((file) =>
      blobToBase64(file).then(
        (contents) => [file.name, contents] as [string, string],
      ),
    ),
  );
}
