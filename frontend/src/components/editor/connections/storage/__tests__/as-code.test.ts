/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { prefixSecret } from "../../secrets";
import { generateStorageCode } from "../as-code";
import type { StorageConnection } from "../schemas";

describe("generateStorageCode", () => {
  const baseS3: StorageConnection = {
    type: "s3",
    bucket: "my-bucket",
    region: "us-east-1",
    access_key_id: "AKIAIOSFODNN7EXAMPLE",
    secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    endpoint_url: undefined,
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

  const baseGDrive: StorageConnection = {
    type: "gdrive",
    credentials_json:
      '{"type": "service_account", "client_email": "test@test.iam.gserviceaccount.com"}',
  };

  describe("S3", () => {
    it("basic connection with all fields", () => {
      expect(generateStorageCode(baseS3, "obstore")).toMatchSnapshot();
    });

    it("minimal connection (bucket only)", () => {
      const conn: StorageConnection = {
        type: "s3",
        bucket: "my-bucket",
      };
      expect(generateStorageCode(conn, "obstore")).toMatchSnapshot();
    });

    it("with custom endpoint", () => {
      const conn: StorageConnection = {
        ...baseS3,
        endpoint_url: "https://minio.example.com:9000",
      };
      expect(generateStorageCode(conn, "obstore")).toMatchSnapshot();
    });

    it("with secrets", () => {
      const conn: StorageConnection = {
        type: "s3",
        bucket: "my-bucket",
        region: "us-east-1",
        access_key_id: prefixSecret("AWS_ACCESS_KEY_ID"),
        secret_access_key: prefixSecret("AWS_SECRET_ACCESS_KEY"),
      };
      expect(generateStorageCode(conn, "obstore")).toMatchSnapshot();
    });
  });

  describe("GCS", () => {
    it("with service account key", () => {
      expect(generateStorageCode(baseGCS, "obstore")).toMatchSnapshot();
    });

    it("without service account key (default credentials)", () => {
      const conn: StorageConnection = {
        type: "gcs",
        bucket: "my-bucket",
      };
      expect(generateStorageCode(conn, "obstore")).toMatchSnapshot();
    });
  });

  describe("Azure", () => {
    it("basic connection with account key", () => {
      expect(generateStorageCode(baseAzure, "obstore")).toMatchSnapshot();
    });

    it("without account key", () => {
      const conn: StorageConnection = {
        type: "azure",
        container: "my-container",
        account_name: "storageaccount",
      };
      expect(generateStorageCode(conn, "obstore")).toMatchSnapshot();
    });

    it("with secrets", () => {
      const conn: StorageConnection = {
        type: "azure",
        container: "my-container",
        account_name: prefixSecret("AZURE_ACCOUNT"),
        account_key: prefixSecret("AZURE_KEY"),
      };
      expect(generateStorageCode(conn, "obstore")).toMatchSnapshot();
    });
  });

  describe("Google Drive", () => {
    it("with service account credentials", () => {
      expect(generateStorageCode(baseGDrive, "fsspec")).toMatchSnapshot();
    });

    it("with browser auth (no credentials)", () => {
      const conn: StorageConnection = {
        type: "gdrive",
      };
      expect(generateStorageCode(conn, "fsspec")).toMatchSnapshot();
    });
  });

  describe("invalid cases", () => {
    it("throws for empty S3 bucket", () => {
      expect(() =>
        generateStorageCode(
          { type: "s3", bucket: "" } as StorageConnection,
          "obstore",
        ),
      ).toThrow();
    });

    it("throws for empty GCS bucket", () => {
      expect(() =>
        generateStorageCode(
          { type: "gcs", bucket: "" } as StorageConnection,
          "obstore",
        ),
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
          "obstore",
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
          "obstore",
        ),
      ).toThrow();
    });
  });
});
