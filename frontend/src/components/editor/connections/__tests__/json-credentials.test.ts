/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import {
  escapePythonString,
  flattenSecretValue,
  looksLikeJson,
  resolveJsonCredential,
} from "../json-credentials";
import { prefixPath } from "../paths";
import { prefixSecret } from "../secrets";

describe("resolveJsonCredential", () => {
  test("resolves a file path", () => {
    expect(
      resolveJsonCredential(prefixPath("/etc/secrets/key.json"), (v) => v),
    ).toEqual({ kind: "path", path: "/etc/secrets/key.json" });
  });

  test("resolves a secret via printSecret", () => {
    expect(
      resolveJsonCredential(prefixSecret("MY_CREDS"), () => "_my_creds"),
    ).toEqual({ kind: "json", expr: "json.loads(_my_creds)" });
  });

  test("resolves a raw JSON literal", () => {
    expect(
      resolveJsonCredential('{"type":"service_account"}', (v) => v),
    ).toEqual({
      kind: "json",
      expr: 'json.loads(r"""{"type":"service_account"}""")',
    });
  });

  test("uses a raw string so escaped newlines in a private_key survive", () => {
    const credentialsJson =
      '{"private_key":"-----BEGIN PRIVATE KEY-----\\nabc123\\n-----END PRIVATE KEY-----\\n"}';
    const credential = resolveJsonCredential(credentialsJson, (v) => v);
    expect(credential).toEqual({
      kind: "json",
      expr: `json.loads(r"""${credentialsJson}""")`,
    });
  });

  test("prefers path over secret-looking values", () => {
    // A path-prefixed value wins even if the path text starts with "env:".
    expect(
      resolveJsonCredential(prefixPath("env:not-a-secret"), (v) => v),
    ).toEqual({ kind: "path", path: "env:not-a-secret" });
  });
});

describe("looksLikeJson", () => {
  test("detects objects and arrays, including partial paste", () => {
    expect(looksLikeJson('{"type":"service_account"}')).toBe(true);
    expect(looksLikeJson("  {")).toBe(true);
    expect(looksLikeJson("[1, 2]")).toBe(true);
    expect(looksLikeJson("/etc/secrets/key.json")).toBe(false);
    expect(looksLikeJson("MY_SECRET")).toBe(false);
    expect(looksLikeJson("")).toBe(false);
  });

  test("drives the path vs. create-secret combobox actions exclusively", () => {
    // These mirror how SECRET_TEXTAREA_RENDERER wires allowCustomValue /
    // allowCreateSecret, so a path and a JSON paste never both offer (or
    // both hide) the wrong action.
    const allowCustomValue = (search: string) => !looksLikeJson(search);
    const allowCreateSecret = (search: string) =>
      !search || looksLikeJson(search);

    expect(allowCustomValue("/etc/secrets/key.json")).toBe(true);
    expect(allowCreateSecret("/etc/secrets/key.json")).toBe(false);

    expect(allowCustomValue('{"type":"service_account"}')).toBe(false);
    expect(allowCreateSecret('{"type":"service_account"}')).toBe(true);

    expect(allowCreateSecret("")).toBe(true);
  });
});

describe("flattenSecretValue", () => {
  test("minifies valid JSON", () => {
    expect(
      flattenSecretValue(`{
  "type": "service_account",
  "project_id": "test"
}`),
    ).toBe('{"type":"service_account","project_id":"test"}');
  });

  test("strips newlines from non-JSON", () => {
    expect(flattenSecretValue("line1\nline2\r\nline3")).toBe("line1line2line3");
  });

  test("returns empty for blank input", () => {
    expect(flattenSecretValue("")).toBe("");
    expect(flattenSecretValue("   \n  ")).toBe("");
  });
});

describe("escapePythonString", () => {
  test("escapes backslashes and quotes", () => {
    expect(escapePythonString('C:\\tmp\\"creds".json')).toBe(
      'C:\\\\tmp\\\\\\"creds\\".json',
    );
    expect(escapePythonString("/etc/secrets/key.json")).toBe(
      "/etc/secrets/key.json",
    );
  });

  test("escapes control characters", () => {
    expect(escapePythonString("line1\nline2")).toBe("line1\\nline2");
    expect(escapePythonString("a\tb\rc")).toBe("a\\tb\\rc");
  });
});
