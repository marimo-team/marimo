/* Copyright 2024 Marimo. All rights reserved. */

export enum OperationType {
  INSERT = "insert",
  DELETE = "delete",
  SUBSTITUTE = "substitute",
  MATCH = "match",
}

export interface EditOperation<T> {
  type: OperationType;
  position: number;
  element?: T;
  originalElement?: T;
}

export interface EditDistanceResult<T> {
  distance: number;
  operations: Array<EditOperation<T>>;
}

// Original edit distance function (for comparison)
export function editDistance<T, U>(
  arr1: T[],
  arr2: U[],
  equals: (a: T, b: U) => boolean = (a, b) => a === b,
): EditDistanceResult<T> {
  const m = arr1.length;
  const n = arr2.length;

  const dp: number[][] = new Array(m + 1)
    .fill(null)
    .map(() => new Array(n + 1).fill(0));

  for (let i = 0; i <= m; i++) {
    dp[i][0] = i;
  }
  for (let j = 0; j <= n; j++) {
    dp[0][j] = j;
  }

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = equals(arr1[i - 1], arr2[j - 1])
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }

  // Backtrack for operations
  const operations: Array<EditOperation<T>> = [];
  let i = m,
    j = n;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && equals(arr1[i - 1], arr2[j - 1])) {
      operations.unshift({
        type: OperationType.MATCH,
        position: i - 1,
        element: arr1[i - 1],
      });
      i--;
      j--;
    } else if (i > 0 && j > 0 && dp[i][j] === dp[i - 1][j - 1] + 1) {
      operations.unshift({
        type: OperationType.SUBSTITUTE,
        position: i - 1,
        element: arr2[j - 1],
        originalElement: arr1[i - 1],
      });
      i--;
      j--;
    } else if (i > 0 && dp[i][j] === dp[i - 1][j] + 1) {
      operations.unshift({
        type: OperationType.DELETE,
        position: i - 1,
        originalElement: arr1[i - 1],
      });
      i--;
    } else if (j > 0 && dp[i][j] === dp[i][j - 1] + 1) {
      operations.unshift({
        type: OperationType.INSERT,
        position: i,
        element: arr2[j - 1],
      });
      j--;
    }
  }

  return { distance: dp[m][n], operations };
}

// Function to apply operations with stub for inserts/substitutions
export function applyOperationsWithStub<T>(
  originalArray: T[],
  operations: Array<EditOperation<T>>,
  stub: T,
): T[] {
  const result: T[] = [];
  let originalIndex = 0;

  for (const op of operations) {
    switch (op.type) {
      case OperationType.MATCH:
        // Copy the original element
        result.push(originalArray[originalIndex]);
        originalIndex++;
        break;

      case OperationType.DELETE:
        // Skip the original element (don't add to result)
        originalIndex++;
        break;

      case OperationType.INSERT:
        // Add stub for inserted element
        result.push(stub);
        break;

      case OperationType.SUBSTITUTE:
        // Add stub for substituted element
        result.push(stub);
        originalIndex++;
        break;
    }
  }

  return result;
}

// Generic function to merge cell arrays by code content
export function mergeArray<T, U>(
  arr1: T[],
  arr2: U[],
  equals: (a: T, b: U) => boolean,
  stub: T,
): { merged: Array<T | null>; edits: EditDistanceResult<T> } {
  // Use edit distance on code content - cast arr2 to T for comparison
  const edits = editDistance(arr1, arr2 as unknown as T[], (a, b) =>
    equals(a, b as unknown as U),
  );
  // Apply operations to session cells to match notebook structure
  return {
    merged: applyOperationsWithStub(arr1, edits.operations, stub),
    edits,
  };
}
