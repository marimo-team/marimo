/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Get the protocol and parent directories of a path.
 */
export function getProtocolAndParentDirectories(
  path: string,
  delimiter: string,
  initialPath: string,
  restrictNavigation: boolean,
) {
  // Determine protocol (http://, gs://, C:\, or /)
  const protocolMatch = path.match(/^[A-Za-z]+:\/\//);
  const isWindowsPath = /^[A-Za-z]:\\/.test(path);
  const protocol = protocolMatch
    ? protocolMatch[0]
    : isWindowsPath
      ? path.slice(0, 3)
      : "/";

  // Remove protocol from path
  const pathWithoutProtocol = isWindowsPath
    ? path.slice(protocol.length)
    : protocolMatch
      ? path.slice(protocol.length)
      : path;

  // Split path into segments
  const segments = pathWithoutProtocol.split(delimiter).filter(Boolean);

  // Build parent directories from segments
  let parentDirectories: string[] = [];

  if (isWindowsPath) {
    // Handle Windows paths differently
    for (let i = segments.length; i >= 0; i--) {
      const dirPath = protocol + segments.slice(0, i).join(delimiter);
      parentDirectories.push(dirPath);
    }
  } else {
    // Handle non-Windows paths
    let currentPath = protocol;
    for (let i = 0; i <= segments.length; i++) {
      const dirPath = currentPath + segments.slice(0, i).join(delimiter);
      parentDirectories.push(dirPath);

      // Add delimiter if not already present
      if (i < segments.length && !currentPath.endsWith(delimiter)) {
        currentPath += delimiter;
      }
    }
    // Reverse to get parent directories in descending order
    parentDirectories.reverse();
  }

  // Filter to paths within initial path if navigation is restricted
  if (restrictNavigation) {
    parentDirectories = parentDirectories.filter((dir) =>
      dir.startsWith(initialPath),
    );
  }

  return { protocol, parentDirectories };
}
