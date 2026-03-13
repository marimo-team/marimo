/* Copyright 2026 Marimo. All rights reserved. */
import { z } from "zod";
import { FieldOptions } from "@/components/forms/options";

export const S3StorageSchema = z
  .object({
    type: z.literal("s3"),
    bucket: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Bucket",
          placeholder: "my-bucket",
        }),
      ),
    region: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Region",
          placeholder: "us-east-1",
          optionRegex: ".*region.*",
        }),
      ),
    access_key_id: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Access Key ID",
          inputType: "password",
          optionRegex: ".*access_key.*",
        }),
      ),
    secret_access_key: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Secret Access Key",
          inputType: "password",
          optionRegex: ".*secret.*access.*",
        }),
      ),
    endpoint_url: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Endpoint URL",
          placeholder: "https://s3.amazonaws.com",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const GCSStorageSchema = z
  .object({
    type: z.literal("gcs"),
    bucket: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Bucket",
          placeholder: "my-bucket",
        }),
      ),
    service_account_key: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Service Account Key (JSON)",
          inputType: "textarea",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const AzureStorageSchema = z
  .object({
    type: z.literal("azure"),
    container: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Container",
          placeholder: "my-container",
        }),
      ),
    account_name: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Account Name",
          placeholder: "storageaccount",
          optionRegex: ".*account.*",
        }),
      ),
    account_key: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Account Key",
          inputType: "password",
          optionRegex: ".*azure.*key.*",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const GoogleDriveStorageSchema = z
  .object({
    type: z.literal("gdrive"),
    credentials_json: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Service Account JSON",
          description: "Leave empty to use browser-based authentication",
          inputType: "textarea",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const StorageConnectionSchema = z.discriminatedUnion("type", [
  S3StorageSchema,
  GCSStorageSchema,
  AzureStorageSchema,
  GoogleDriveStorageSchema,
]);

export type StorageConnection = z.infer<typeof StorageConnectionSchema>;
