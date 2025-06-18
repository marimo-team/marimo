/* Copyright 2024 Marimo. All rights reserved. */

export enum OperationType {
  INSERT = "insert",
  DELETE = "delete",
  SUBSTITUTE = "substitute",
  MATCH = "match",
}

export interface EditOperation {
  type: OperationType;
  position: number;
}

export interface EditDistanceResult {
  distance: number;
  operations: EditOperation[];
}

// Very rote LLM produced edit distance implementation.
// Sanity checked in tests, and a few lines here saves a dependency.
export function editDistance<T, U>(
  arr1: T[],
  arr2: U[],
  equals: (a: T, b: U) => boolean = (a, b) => a === b,
): EditDistanceResult {
  const m = arr1.length;
  const n = arr2.length;
  const m1 = m + 1;
  const n1 = n + 1;

  const dp: number[][] = Array.from({ m1 })
    .fill(null)
    .map(() => Array.from({ n1 }).fill(0));

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
  const operations: EditOperation[] = [];
  let i = m;
  let j = n;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && equals(arr1[i - 1], arr2[j - 1])) {
      operations.unshift({
        type: OperationType.MATCH,
        position: i - 1,
      });
      i--;
      j--;
    } else if (i > 0 && j > 0 && dp[i][j] === dp[i - 1][j - 1] + 1) {
      operations.unshift({
        type: OperationType.SUBSTITUTE,
        position: i - 1,
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
      });
      j--;
    }
  }

  return { distance: dp[m][n], operations };
}

// Function to apply operations with stub for inserts/substitutions
export function applyOperationsWithStub<T>(
  originalArray: T[],
  operations: EditOperation[],
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
): { merged: Array<T | null>; edits: EditDistanceResult } {
  const edits = editDistance(arr1, arr2, equals);
  return {
    merged: applyOperationsWithStub(arr1, edits.operations, stub),
    edits,
  };
}
