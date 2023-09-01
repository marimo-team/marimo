/* Copyright 2023 Marimo. All rights reserved. */
export function blobToBase64(file: Blob): Promise<[string, string]> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = (e) => {
      if (e.target !== null && e.target.result !== null) {
        const dataURL = e.target.result as string;
        // Get contents from a string of the form: data:*/*;base64,contents
        const b64EncodedContents = dataURL.slice(dataURL.indexOf(",") + 1);
        resolve([file.name, b64EncodedContents]);
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
  return Promise.all(files.map((file) => blobToBase64(file)));
}
