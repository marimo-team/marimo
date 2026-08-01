/* Copyright 2026 Marimo. All rights reserved. */

import dedent from "string-dedent";
import { assertNever } from "@/utils/assertNever";
import { escapePythonString, resolveJsonCredential } from "../json-credentials";
import { isSecret, unprefixSecret } from "../secrets";
import {
  type S3Auth,
  type StorageConnection,
  StorageConnectionSchema,
} from "./schemas";

export type StorageLibrary = "obstore" | "fsspec" | "huggingface_hub";

export interface StorageCodeOptions {
  library: StorageLibrary;
  isEmbedded?: boolean;
}

export const StorageLibraryDisplayNames: Record<StorageLibrary, string> = {
  obstore: "obstore",
  fsspec: "fsspec",
  huggingface_hub: "huggingface_hub",
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

/**
 * Credential kwargs shared by every S3-compatible store.
 */
function s3AuthParams(
  auth: S3Auth | undefined,
  secrets: SecretContainer,
): string[] {
  // obstore polls the credential endpoint with the token read from the file,
  // refreshing credentials for the lifetime of the store.
  if (auth?.type === "Container credentials") {
    return [
      `    container_credentials_full_uri=${secrets.print("container_credentials_full_uri", auth.container_credentials_full_uri)},`,
      `    container_authorization_token_file=${secrets.print("container_authorization_token_file", auth.container_authorization_token_file)},`,
    ];
  }

  const params: string[] = [];
  if (auth?.access_key_id) {
    params.push(
      `    access_key_id=${secrets.print("access_key_id", auth.access_key_id)},`,
    );
  }
  if (auth?.secret_access_key) {
    params.push(
      `    secret_access_key=${secrets.print("secret_access_key", auth.secret_access_key)},`,
    );
  }
  return params;
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
  params.push(...s3AuthParams(connection.auth, secrets));
  if (connection.endpoint_url) {
    params.push(
      `    endpoint_url=${secrets.print("endpoint_url", connection.endpoint_url)},`,
    );
  }
  if (connection.allow_http) {
    params.push("    allow_http=True,");
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

  if (!connection.service_account_key) {
    return {
      imports,
      code: dedent(`
        store = GCSStore(${bucket})
      `),
    };
  }

  const credential = resolveJsonCredential(
    connection.service_account_key,
    (v) => secrets.print("service_account_key", v),
  );

  if (credential.kind === "path") {
    const code = dedent(`
      store = GCSStore(${bucket},
          service_account_path="${escapePythonString(credential.path)}",
      )
    `);
    return { imports, code };
  }

  imports.add("import json");
  const code = dedent(`
    _credentials = ${credential.expr}
    store = GCSStore(${bucket},
        service_account_key=_credentials,
    )
  `);
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

  params.push(...s3AuthParams(connection.auth, secrets));

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
  options: { secrets: SecretContainer; isEmbedded?: boolean },
): { imports: Set<string>; code: string } {
  /**
   * Skip instance cache True so you can create multiple connections which don't reference the same creds.
   * Use listings cache False so we don't get stale reads.
   */
  const { secrets, isEmbedded = false } = options;
  const imports = new Set(["from gdrive_fsspec import GoogleDriveFileSystem"]);

  if (connection.credentials_json) {
    const credential = resolveJsonCredential(connection.credentials_json, (v) =>
      secrets.print("credentials_json", v),
    );
    // gdrive-fsspec accepts a filesystem path as `creds` when the string
    // doesn't start with "{"; otherwise it expects a JSON object/string.
    if (credential.kind === "path") {
      const code = dedent(`
        fs = GoogleDriveFileSystem(creds="${escapePythonString(credential.path)}", token="service_account", use_listings_cache=False, skip_instance_cache=True)
      `);
      return { imports, code };
    }
    imports.add("import json");
    const code = dedent(`
      _creds = ${credential.expr}
      fs = GoogleDriveFileSystem(creds=_creds, token="service_account", use_listings_cache=False, skip_instance_cache=True)
    `);
    return { imports, code };
  }

  // In the iframe (embedded) flow we authenticate via the console-based OOB
  // flow, which prints an auth URL and reads the code from stdin. Clear the
  // console afterwards so the (single-use) auth code doesn't linger.
  const code = isEmbedded
    ? dedent(`
        fs = GoogleDriveFileSystem(use_listings_cache=False, skip_instance_cache=True, auth_kwargs={"use_local_webserver": False})
        mo.output.clear_console()
      `)
    : dedent(`
        fs = GoogleDriveFileSystem(use_listings_cache=False, skip_instance_cache=True)
      `);
  return { imports, code };
}

function generateHuggingfaceCode(
  connection: Extract<StorageConnection, { type: "huggingface" }>,
  secrets: SecretContainer,
): { imports: Set<string>; code: string } {
  const imports = new Set(["from huggingface_hub import HfApi"]);

  if (!connection.token) {
    return { imports, code: "hf = HfApi()" };
  }

  const token = secrets.print("token", connection.token);
  return { imports, code: `hf = HfApi(token=${token})` };
}

export function generateStorageCode(
  connection: StorageConnection,
  options: StorageCodeOptions,
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
      result = generateGDriveCode(connection, {
        secrets,
        isEmbedded: options.isEmbedded,
      });
      break;
    case "huggingface":
      result = generateHuggingfaceCode(connection, secrets);
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
