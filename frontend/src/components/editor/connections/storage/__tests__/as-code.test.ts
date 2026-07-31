/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { prefixPath } from "../../paths";
import { prefixSecret } from "../../secrets";
import { generateStorageCode } from "../as-code";
import type { StorageConnection } from "../schemas";

describe("generateStorageCode", () => {
  const baseS3: StorageConnection = {
    type: "s3",
    bucket: "my-bucket",
    region: "us-east-1",
    endpoint_url: undefined,
    allow_http: false,
    auth: {
      type: "Access keys",
      access_key_id: "AKIAIOSFODNN7EXAMPLE",
      secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    },
  };

  const baseGCS: StorageConnection = {
    type: "gcs",
    bucket: "my-bucket",
    service_account_key: '{"type": "service_account", "project_id": "test"}',
  };

  const baseAzure: StorageConnection = {
    type: "azure",
    container: "my-container",
    account_name: "storageaccount",
    account_key: "base64accountkey==",
  };

  const baseCoreWeave: StorageConnection = {
    type: "coreweave",
    bucket: "operator-bucket",
    region: "US-EAST-04A",
    auth: {
      type: "Access keys",
      access_key_id: "AKIAIOSFODNN7EXAMPLE",
      secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    },
  };

  const baseGDrive: StorageConnection = {
    type: "gdrive",
    credentials_json:
      '{"type": "service_account", "client_email": "test@test.iam.gserviceaccount.com"}',
  };

  describe("S3", () => {
    it("basic connection with all fields", () => {
      expect(
        generateStorageCode(baseS3, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("minimal connection (bucket only)", () => {
      const conn: StorageConnection = {
        type: "s3",
        bucket: "my-bucket",
        allow_http: false,
        auth: { type: "Access keys" },
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with custom endpoint", () => {
      const conn: StorageConnection = {
        ...baseS3,
        endpoint_url: "https://minio.example.com:9000",
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with plain-http endpoint", () => {
      const conn: StorageConnection = {
        ...baseS3,
        endpoint_url: "http://cwlota.com",
        allow_http: true,
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with container credentials", () => {
      const conn: StorageConnection = {
        ...baseS3,
        auth: {
          type: "Container credentials",
          container_credentials_full_uri:
            "http://169.254.170.23/v1/credentials",
          container_authorization_token_file: "/var/run/secrets/token",
        },
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with container credentials from secrets", () => {
      const conn: StorageConnection = {
        ...baseS3,
        auth: {
          type: "Container credentials",
          container_credentials_full_uri: prefixSecret(
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
          ),
          container_authorization_token_file: prefixSecret(
            "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
          ),
        },
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with secrets", () => {
      const conn: StorageConnection = {
        type: "s3",
        bucket: "my-bucket",
        region: "us-east-1",
        allow_http: false,
        auth: {
          type: "Access keys",
          access_key_id: prefixSecret("AWS_ACCESS_KEY_ID"),
          secret_access_key: prefixSecret("AWS_SECRET_ACCESS_KEY"),
        },
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });
  });

  describe("GCS", () => {
    it("with service account key", () => {
      expect(
        generateStorageCode(baseGCS, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("without service account key (default credentials)", () => {
      const conn: StorageConnection = {
        type: "gcs",
        bucket: "my-bucket",
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with service account key from secrets", () => {
      const conn: StorageConnection = {
        ...baseGCS,
        service_account_key: prefixSecret("GCS_SERVICE_ACCOUNT_KEY"),
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with service account key from a file path", () => {
      const conn: StorageConnection = {
        ...baseGCS,
        service_account_key: prefixPath("/etc/secrets/gcs.json"),
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });
  });

  describe("Azure", () => {
    it("basic connection with account key", () => {
      expect(
        generateStorageCode(baseAzure, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("without account key", () => {
      const conn: StorageConnection = {
        type: "azure",
        container: "my-container",
        account_name: "storageaccount",
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with secrets", () => {
      const conn: StorageConnection = {
        type: "azure",
        container: "my-container",
        account_name: prefixSecret("AZURE_ACCOUNT"),
        account_key: prefixSecret("AZURE_KEY"),
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });
  });

  describe("CoreWeave", () => {
    it("basic connection with all fields", () => {
      expect(
        generateStorageCode(baseCoreWeave, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("minimal connection (bucket and region only)", () => {
      const conn: StorageConnection = {
        type: "coreweave",
        bucket: "operator-bucket",
        region: "US-EAST-04A",
        auth: { type: "Access keys" },
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with container credentials", () => {
      const conn: StorageConnection = {
        ...baseCoreWeave,
        auth: {
          type: "Container credentials",
          container_credentials_full_uri: prefixSecret(
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
          ),
          container_authorization_token_file: prefixSecret(
            "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
          ),
        },
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });

    it("with secrets", () => {
      const conn: StorageConnection = {
        type: "coreweave",
        bucket: "operator-bucket",
        region: "US-EAST-04A",
        auth: {
          type: "Access keys",
          access_key_id: prefixSecret("COREWEAVE_OBJECT_STORAGE_KEY"),
          secret_access_key: prefixSecret("COREWEAVE_OBJECT_STORAGE_SECRET"),
        },
      };
      expect(
        generateStorageCode(conn, { library: "obstore" }),
      ).toMatchSnapshot();
    });
  });

  describe("Google Drive", () => {
    it("with service account credentials", () => {
      expect(
        generateStorageCode(baseGDrive, { library: "fsspec" }),
      ).toMatchSnapshot();
    });

    it("with default auth (no credentials)", () => {
      const conn: StorageConnection = {
        type: "gdrive",
      };
      expect(
        generateStorageCode(conn, { library: "fsspec" }),
      ).toMatchSnapshot();
    });

    it("with embedded auth (no credentials)", () => {
      const conn: StorageConnection = {
        type: "gdrive",
      };
      expect(
        generateStorageCode(conn, { library: "fsspec", isEmbedded: true }),
      ).toMatchSnapshot();
    });

    it("with service account credentials from secrets", () => {
      const conn: StorageConnection = {
        ...baseGDrive,
        credentials_json: prefixSecret("GDRIVE_CREDENTIALS_JSON"),
      };
      expect(
        generateStorageCode(conn, { library: "fsspec" }),
      ).toMatchSnapshot();
    });

    it("with service account credentials from a file path", () => {
      const conn: StorageConnection = {
        ...baseGDrive,
        credentials_json: prefixPath("/etc/secrets/gdrive.json"),
      };
      expect(
        generateStorageCode(conn, { library: "fsspec" }),
      ).toMatchSnapshot();
    });
  });

  describe("Hugging Face", () => {
    it("default connection", () => {
      expect(
        generateStorageCode({ type: "huggingface" }, { library: "fsspec" }),
      ).toMatchSnapshot();
    });

    it("with token from secrets", () => {
      expect(
        generateStorageCode(
          {
            type: "huggingface",
            token: prefixSecret("HF_TOKEN"),
          },
          { library: "fsspec" },
        ),
      ).toMatchSnapshot();
    });
  });

  describe("invalid cases", () => {
    it("throws for empty S3 bucket", () => {
      expect(() =>
        generateStorageCode({ type: "s3", bucket: "" } as StorageConnection, {
          library: "obstore",
        }),
      ).toThrow();
    });

    it("throws for empty GCS bucket", () => {
      expect(() =>
        generateStorageCode({ type: "gcs", bucket: "" } as StorageConnection, {
          library: "obstore",
        }),
      ).toThrow();
    });

    it("throws for empty Azure container", () => {
      expect(() =>
        generateStorageCode(
          {
            type: "azure",
            container: "",
            account_name: "acct",
          } as StorageConnection,
          { library: "obstore" },
        ),
      ).toThrow();
    });

    it("throws for empty Azure account name", () => {
      expect(() =>
        generateStorageCode(
          {
            type: "azure",
            container: "my-container",
            account_name: "",
          } as StorageConnection,
          { library: "obstore" },
        ),
      ).toThrow();
    });

    it("throws for empty CoreWeave bucket", () => {
      expect(() =>
        generateStorageCode(
          {
            type: "coreweave",
            bucket: "",
            region: "US-EAST-04A",
          } as StorageConnection,
          { library: "obstore" },
        ),
      ).toThrow();
    });

    it("throws for empty CoreWeave region", () => {
      expect(() =>
        generateStorageCode(
          {
            type: "coreweave",
            bucket: "operator-bucket",
            region: "",
          } as StorageConnection,
          { library: "obstore" },
        ),
      ).toThrow();
    });
  });
});
