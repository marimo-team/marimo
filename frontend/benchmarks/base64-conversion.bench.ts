import { bench, describe } from "vitest";

// To run:
// pnpm vitest bench benchmarks/base64-conversion.bench.ts

// Helper to convert Uint8Array to base64
function uint8ArrayToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

// Slow implementation (using Uint8Array.from)
function base64ToUint8ArraySlow(bytes: string): Uint8Array {
  const binary = window.atob(bytes);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

// Fast implementation (using manual loop)
function base64ToUint8ArrayFast(bytes: string): Uint8Array {
  const binary = window.atob(bytes);
  const len = binary.length;
  const uint8Array = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    uint8Array[i] = binary.charCodeAt(i);
  }
  return uint8Array;
}

// Test data setup
const sizes = {
  small: 1024, // 1KB
  medium: 10 * 1024, // 10KB
  large: 100 * 1024, // 100KB
  xlarge: 1024 * 1024, // 1MB
};

const testData: Record<string, string> = {};
for (const [name, size] of Object.entries(sizes)) {
  const data = new Uint8Array(size);
  for (let i = 0; i < size; i++) {
    data[i] = i % 256;
  }
  testData[name] = uint8ArrayToBase64(data);
}

// Benchmarks
describe("base64 to Uint8Array conversion", () => {
  for (const [name, base64] of Object.entries(testData)) {
    bench(`slow - ${name}`, () => {
      base64ToUint8ArraySlow(base64);
    });

    bench(`fast - ${name}`, () => {
      base64ToUint8ArrayFast(base64);
    });
  }
});
