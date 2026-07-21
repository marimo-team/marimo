/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import { partitionSecretKeys } from "../secret-combobox";

describe("partitionSecretKeys", () => {
  const keys = [
    "HOSTNAME",
    "PGHOST",
    "DB_HOST",
    "KUBERNETES_SERVICE_HOST",
    "GPG_KEY",
    "HOME",
    "POSTGRES_PASSWORD",
    "DB_PASSWORD",
    "USERNAME",
    "PGUSER",
    "USER_AGENT",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "OBJECT_STORAGE_KEY",
    "OBJECT_STORAGE_SECRET",
    "DATABASE_URL",
    "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE",
  ];

  test("returns all keys as other when regex is empty", () => {
    expect(partitionSecretKeys(keys, "")).toEqual({
      recommended: [],
      other: keys,
    });
  });

  test("handles invalid regex", () => {
    expect(partitionSecretKeys(keys, "[invalid")).toEqual({
      recommended: [],
      other: keys,
    });
  });

  test("recommends host-like keys and excludes kubernetes", () => {
    const hostRegex =
      "^(?!.*(kubernetes|gpg)).*(host(name)?|pghost|db.?host|database.?host|mysql.?host|postgres.?host|server.?host)";
    const { recommended, other } = partitionSecretKeys(keys, hostRegex);

    expect(recommended).toEqual(["HOSTNAME", "PGHOST", "DB_HOST"]);
    expect(other).toContain("KUBERNETES_SERVICE_HOST");
    expect(other).toContain("GPG_KEY");
    expect(other).toContain("HOME");
  });

  test("recommends password-like keys", () => {
    const { recommended } = partitionSecretKeys(
      keys,
      "(password|passwd|pgpassword|db.?pass(word)?)",
    );
    expect(recommended).toEqual(["POSTGRES_PASSWORD", "DB_PASSWORD"]);
  });

  test("recommends username keys without matching USER_AGENT", () => {
    const { recommended } = partitionSecretKeys(
      keys,
      "(username|pguser|db.?user|^USER$|_USER$)",
    );
    expect(recommended).toEqual(["USERNAME", "PGUSER"]);
    expect(recommended).not.toContain("USER_AGENT");
  });

  test("recommends aws access key id without matching the secret key", () => {
    const { recommended } = partitionSecretKeys(
      keys,
      "(access.?key.?id|aws.?access.?key)",
    );
    expect(recommended).toEqual(["AWS_ACCESS_KEY_ID"]);
  });

  test("recommends aws secret access key", () => {
    const { recommended } = partitionSecretKeys(
      keys,
      "(secret.?access.?key|aws.?secret)",
    );
    expect(recommended).toEqual(["AWS_SECRET_ACCESS_KEY"]);
  });

  test("recommends aws session token", () => {
    const { recommended } = partitionSecretKeys(
      keys,
      "(session.?token|aws.?session)",
    );
    expect(recommended).toEqual(["AWS_SESSION_TOKEN"]);
  });

  test("recommends object storage credentials", () => {
    expect(
      partitionSecretKeys(
        keys,
        "(access.?key.?id|object.?storage.?key|aws.?access.?key)",
      ).recommended,
    ).toEqual(["AWS_ACCESS_KEY_ID", "OBJECT_STORAGE_KEY"]);
    expect(
      partitionSecretKeys(
        keys,
        "(secret.?access.?key|object.?storage.?secret|aws.?secret)",
      ).recommended,
    ).toEqual(["AWS_SECRET_ACCESS_KEY", "OBJECT_STORAGE_SECRET"]);
  });

  test("recommends uri/url-like keys", () => {
    const { recommended } = partitionSecretKeys(
      keys,
      "(uri|url|connection.?string|database.?url|jdbc)",
    );
    expect(recommended).toEqual(["DATABASE_URL"]);
  });

  test("recommends passphrase keys", () => {
    const { recommended } = partitionSecretKeys(
      keys,
      "(passphrase|private.?key.?passphrase|key.?passphrase)",
    );
    expect(recommended).toEqual(["SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"]);
  });
});
