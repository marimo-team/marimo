/* Copyright 2026 Marimo. All rights reserved. */
import { z } from "zod";
import { FieldOptions } from "@/components/forms/options";

/**
 * Credentials shared by every S3-compatible store (Amazon S3, CoreWeave, ...).
 *
 * Rendered as tabs: either long-lived access keys, or a credential-vending
 * endpoint (ECS/EKS task roles, CoreWeave sandboxes, ...) that obstore polls
 * with a bearer token read from disk.
 */
const s3AuthField = () =>
  z
    .discriminatedUnion("type", [
      z.object({
        type: z.literal("Access keys"),
        access_key_id: z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "Access Key ID",
              description: "Leave empty to use the default credential chain",
              inputType: "password",
              optionRegex:
                "(access.?key.?id|object.?storage.?key|aws.?access.?key)",
            }),
          ),
        secret_access_key: z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "Secret Access Key",
              inputType: "password",
              optionRegex:
                "(secret.?access.?key|object.?storage.?secret|aws.?secret)",
            }),
          ),
      }),
      z.object({
        type: z.literal("Container credentials"),
        container_credentials_full_uri: z
          .string()
          .nonempty()
          .describe(
            FieldOptions.of({
              label: "Credentials URI",
              description: "Endpoint that vends credentials to the container",
              placeholder: "http://169.254.170.23/v1/credentials",
              optionRegex: "container.?credentials",
            }),
          ),
        container_authorization_token_file: z
          .string()
          .nonempty()
          .describe(
            FieldOptions.of({
              label: "Authorization Token File",
              description: "File holding the token sent to the credentials URI",
              placeholder: "/var/run/secrets/token",
              optionRegex:
                "(container.?authorization.?token.?file|container.?auth.?token)",
            }),
          ),
      }),
    ])
    .default({ type: "Access keys" })
    .describe(FieldOptions.of({ label: "Credentials", special: "tabs" }));

const allowHttpField = () =>
  z
    .boolean()
    .default(false)
    .describe(
      FieldOptions.of({
        label: "Allow HTTP",
        description: "Required for plain-http (non-TLS) endpoints",
      }),
    );

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
          optionRegex: "(bucket|s3.?bucket)",
        }),
      ),
    region: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Region",
          placeholder: "us-east-1",
          optionRegex: "(region|aws.?region)",
        }),
      ),
    endpoint_url: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Endpoint URL",
          description:
            "Ignored if the AWS_ENDPOINT_URL_S3 environment variable is set",
          placeholder: "https://s3.amazonaws.com",
          optionRegex: "(endpoint|s3.?url|s3.?endpoint)",
        }),
      ),
    allow_http: allowHttpField(),
    auth: s3AuthField(),
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
          optionRegex: "(bucket|gcs.?bucket|google.?bucket)",
        }),
      ),
    service_account_key: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Service Account Key (JSON)",
          special: "secret_textarea",
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
          optionRegex: "(azure.?account|account.?name|storage.?account)",
        }),
      ),
    account_key: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Account Key",
          inputType: "password",
          optionRegex: "(azure.?key|account.?key|storage.?key)",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const CoreWeaveStorageSchema = z
  .object({
    type: z.literal("coreweave"),
    bucket: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Bucket",
          placeholder: "bucket-name",
        }),
      ),
    region: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Region",
          placeholder: "US-EAST-04A",
        }),
      ),
    auth: s3AuthField(),
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
          special: "secret_textarea",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const HuggingfaceStorageSchema = z
  .object({
    type: z.literal("huggingface"),
    token: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Access Token",
          description:
            "Leave empty to use the HF_TOKEN environment variable or cached login",
          inputType: "password",
          optionRegex: "(hf.?token|hugging.?face.?token|hub.?token)",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const StorageConnectionSchema = z.discriminatedUnion("type", [
  S3StorageSchema,
  GCSStorageSchema,
  AzureStorageSchema,
  CoreWeaveStorageSchema,
  GoogleDriveStorageSchema,
  HuggingfaceStorageSchema,
]);

export type StorageConnection = z.infer<typeof StorageConnectionSchema>;
export type S3Auth = Extract<StorageConnection, { type: "s3" }>["auth"];
