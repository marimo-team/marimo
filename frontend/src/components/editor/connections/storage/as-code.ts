/* Copyright 2026 Marimo. All rights reserved. */

import dedent from "string-dedent";
import { assertNever } from "@/utils/assertNever";
import { isSecret, unprefixSecret } from "../secrets";
import { type StorageConnection, StorageConnectionSchema } from "./schemas";

export type StorageLibrary = "obstore" | "fsspec";

export const StorageLibraryDisplayNames: Record<StorageLibrary, string> = {
  obstore: "obstore",
  fsspec: "fsspec",
};

class SecretContainer {
  private secrets: Record<string, string> = {};

  get imports(): Set<string> {
    if (Object.keys(this.secrets).length === 0) {
      return new Set<string>();
    }
    return new Set<string>(["import os"]);
  }

  print(varName: string, value: string | undefined): string {
    if (value === undefined || value === "") {
      return "";
    }
    const privateVar = `_${varName}`;
    if (isSecret(value)) {
      const envVar = unprefixSecret(value);
      this.secrets[privateVar] = `os.environ.get("${envVar}")`;
      return privateVar;
    }
    return `"${value}"`;
  }

  formatSecrets(): string {
    if (Object.keys(this.secrets).length === 0) {
      return "";
    }
    return Object.entries(this.secrets)
      .map(([k, v]) => `${k} = ${v}`)
      .join("\n");
  }
}

function generateS3Code(
  connection: Extract<StorageConnection, { type: "s3" }>,
  secrets: SecretContainer,
): { imports: Set<string>; code: string } {
  const bucket = secrets.print("bucket", connection.bucket);
  const imports = new Set(["from obstore.store import S3Store"]);
  const params: string[] = [];

  if (connection.region) {
    params.push(`    region=${secrets.print("region", connection.region)},`);
  }
  if (connection.access_key_id) {
    params.push(
      `    access_key_id=${secrets.print("access_key_id", connection.access_key_id)},`,
    );
  }
  if (connection.secret_access_key) {
    params.push(
      `    secret_access_key=${secrets.print("secret_access_key", connection.secret_access_key)},`,
    );
  }
  if (connection.endpoint_url) {
    params.push(
      `    endpoint_url=${secrets.print("endpoint_url", connection.endpoint_url)},`,
    );
  }

  const paramsStr = params.length > 0 ? `\n${params.join("\n")}\n` : "";

  const code = dedent(`
    store = S3Store(${bucket},${paramsStr})
  `);
  return { imports, code };
}

function generateGCSCode(
  connection: Extract<StorageConnection, { type: "gcs" }>,
  secrets: SecretContainer,
): { imports: Set<string>; code: string } {
  const bucket = secrets.print("bucket", connection.bucket);
  const imports = new Set(["from obstore.store import GCSStore"]);

  let code: string;
  if (connection.service_account_key) {
    imports.add("import json");
    code = dedent(`
      _credentials = json.loads("""${connection.service_account_key}""")
      store = GCSStore(${bucket},
          service_account_key=_credentials,
      )
    `);
  } else {
    code = dedent(`
      store = GCSStore(${bucket})
    `);
  }
  return { imports, code };
}

function generateAzureCode(
  connection: Extract<StorageConnection, { type: "azure" }>,
  secrets: SecretContainer,
): { imports: Set<string>; code: string } {
  const container = secrets.print("container", connection.container);
  const accountName = secrets.print("account_name", connection.account_name);
  const imports = new Set(["from obstore.store import AzureStore"]);
  const params: string[] = [`account_name=${accountName},`];

  if (connection.account_key) {
    params.push(
      `account_key=${secrets.print("account_key", connection.account_key)},`,
    );
  }

  const paramsStr = params.map((p) => `    ${p}`).join("\n");

  const code = `store = AzureStore(${container},\n${paramsStr}\n)`;
  return { imports, code };
}

function generateCoreWeaveCode(
  connection: Extract<StorageConnection, { type: "coreweave" }>,
  secrets: SecretContainer,
): { imports: Set<string>; code: string } {
  const bucket = secrets.print("bucket", connection.bucket);
  const imports = new Set(["from obstore.store import S3Store"]);
  const params: string[] = [
    `    region=${secrets.print("region", connection.region)},`,
  ];

  if (connection.access_key_id) {
    params.push(
      `    access_key_id=${secrets.print("access_key_id", connection.access_key_id)},`,
    );
  }
  if (connection.secret_access_key) {
    params.push(
      `    secret_access_key=${secrets.print("secret_access_key", connection.secret_access_key)},`,
    );
  }

  params.push(
    `    endpoint="https://${connection.bucket}.cwobject.com",`,
    "    virtual_hosted_style_request=True,",
  );

  const paramsStr = `\n${params.join("\n")}\n`;

  const code = dedent(`
    store = S3Store(${bucket},${paramsStr})
  `);
  return { imports, code };
}

function generateGDriveCode(
  connection: Extract<StorageConnection, { type: "gdrive" }>,
  secrets: SecretContainer,
): { imports: Set<string>; code: string } {
  const imports = new Set(["from gdrive_fsspec import GoogleDriveFileSystem"]);

  if (connection.credentials_json) {
    imports.add("import json");
    const creds = secrets.print(
      "credentials_json",
      connection.credentials_json,
    );
    const code = dedent(`
      _creds = json.loads("""${connection.credentials_json?.startsWith("ENV:") ? `{${creds}}` : connection.credentials_json}""")
      fs = GoogleDriveFileSystem(creds=_creds, token="service_account", use_listings_cache=False)
    `);
    return { imports, code };
  }

  const code = dedent(`
    fs = GoogleDriveFileSystem(token="browser", use_listings_cache=False)
  `);
  return { imports, code };
}

export function generateStorageCode(
  connection: StorageConnection,
  _library: StorageLibrary,
): string {
  StorageConnectionSchema.parse(connection);

  const secrets = new SecretContainer();
  let result: { imports: Set<string>; code: string };

  switch (connection.type) {
    case "s3":
      result = generateS3Code(connection, secrets);
      break;
    case "gcs":
      result = generateGCSCode(connection, secrets);
      break;
    case "azure":
      result = generateAzureCode(connection, secrets);
      break;
    case "coreweave":
      result = generateCoreWeaveCode(connection, secrets);
      break;
    case "gdrive":
      result = generateGDriveCode(connection, secrets);
      break;
    default:
      assertNever(connection);
  }

  const allImports = new Set([...secrets.imports, ...result.imports]);
  const lines = [...allImports].toSorted();
  lines.push("");
  const secretsStr = secrets.formatSecrets();
  if (secretsStr) {
    lines.push(secretsStr);
  }
  lines.push(result.code.trim());
  return lines.join("\n");
}
