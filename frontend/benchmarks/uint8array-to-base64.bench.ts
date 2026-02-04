import { bench, describe } from "vitest";

// To run:
// pnpm vitest bench benchmarks/uint8array-to-base64.bench.ts

// Slow implementation (using Array.from with callback)
function uint8ArrayToBase64Slow(binary: Uint8Array): string {
  const chars = Array.from(binary, (byte) => String.fromCharCode(byte));
  return window.btoa(chars.join(""));
}

// Fast implementation (using manual loop)
function uint8ArrayToBase64Fast(binary: Uint8Array): string {
  let binaryString = "";
  const len = binary.length;
  for (let i = 0; i < len; i++) {
    binaryString += String.fromCharCode(binary[i]);
  }
  return window.btoa(binaryString);
}

// Test data setup
const sizes = {
  small: 1024, // 1KB
  medium: 10 * 1024, // 10KB
  large: 100 * 1024, // 100KB
  xlarge: 1024 * 1024, // 1MB
};

const testData: Record<string, Uint8Array> = {};
for (const [name, size] of Object.entries(sizes)) {
  const data = new Uint8Array(size);
  for (let i = 0; i < size; i++) {
    data[i] = i % 256;
  }
  testData[name] = data;
}

// Benchmarks
describe("Uint8Array to base64 conversion", () => {
  for (const [name, data] of Object.entries(testData)) {
    bench(`slow - ${name}`, () => {
      uint8ArrayToBase64Slow(data);
    });

    bench(`fast - ${name}`, () => {
      uint8ArrayToBase64Fast(data);
    });
  }
});
