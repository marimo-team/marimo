/* Copyright 2026 Marimo. All rights reserved. */

import { useState } from "react";
import type { FieldValues } from "react-hook-form";
import type { z } from "zod";
import { ProtocolIcon } from "@/components/storage/components";
import type { KnownStorageProtocol } from "@/core/storage/types";
import { ConnectionForm, SelectorButton, SelectorGrid } from "../components";
import {
  generateStorageCode,
  type StorageLibrary,
  StorageLibraryDisplayNames,
} from "./as-code";
import {
  AzureStorageSchema,
  CoreWeaveStorageSchema,
  GCSStorageSchema,
  GoogleDriveStorageSchema,
  S3StorageSchema,
  type StorageConnection,
} from "./schemas";

interface StorageProviderSchema {
  name: string;
  schema: z.ZodType<StorageConnection, FieldValues>;
  protocol: string;
  storageLibraries: {
    libraries: StorageLibrary[];
    preferred: StorageLibrary;
  };
}

const BACKGROUND_COLOR = "#232F3E";

const STORAGE_PROVIDERS = [
  {
    name: "Amazon S3",
    schema: S3StorageSchema,
    protocol: "s3",
    storageLibraries: {
      libraries: ["obstore"],
      preferred: "obstore",
    },
  },
  {
    name: "Google Cloud Storage",
    schema: GCSStorageSchema,
    protocol: "gcs",
    storageLibraries: {
      libraries: ["obstore"],
      preferred: "obstore",
    },
  },
  {
    name: "Azure Blob Storage",
    schema: AzureStorageSchema,
    protocol: "azure",
    storageLibraries: {
      libraries: ["obstore"],
      preferred: "obstore",
    },
  },
  {
    name: "CoreWeave",
    schema: CoreWeaveStorageSchema,
    protocol: "coreweave",
    storageLibraries: {
      libraries: ["obstore"],
      preferred: "obstore",
    },
  },
  {
    name: "Google Drive",
    schema: GoogleDriveStorageSchema,
    protocol: "gdrive",
    storageLibraries: {
      libraries: ["fsspec"],
      preferred: "fsspec",
    },
  },
] satisfies StorageProviderSchema[];

const StorageProviderSelector: React.FC<{
  onSelect: (schema: z.ZodType<StorageConnection, FieldValues>) => void;
}> = ({ onSelect }) => {
  return (
    <SelectorGrid>
      {STORAGE_PROVIDERS.map(({ name, schema, protocol }) => (
        <SelectorButton
          key={name}
          name={name}
          color={BACKGROUND_COLOR}
          icon={
            <ProtocolIcon
              protocol={protocol as KnownStorageProtocol}
              forceDark={true}
              className="w-7.5 h-7.5"
            />
          }
          onSelect={() => onSelect(schema)}
        />
      ))}
    </SelectorGrid>
  );
};

export const AddStorageForm: React.FC<{
  onSubmit: () => void;
  header?: React.ReactNode;
}> = ({ onSubmit, header }) => {
  const [selectedSchema, setSelectedSchema] = useState<z.ZodType<
    StorageConnection,
    FieldValues
  > | null>(null);

  if (!selectedSchema) {
    return (
      <>
        {header}
        <div>
          <StorageProviderSelector onSelect={setSelectedSchema} />
        </div>
      </>
    );
  }

  const provider = STORAGE_PROVIDERS.find((p) => p.schema === selectedSchema);
  const libs = provider?.storageLibraries;

  return (
    <ConnectionForm<StorageConnection, StorageLibrary>
      schema={selectedSchema}
      libraries={libs?.libraries ?? []}
      preferredLibrary={libs?.preferred ?? "obstore"}
      displayNames={StorageLibraryDisplayNames}
      libraryLabel="Preferred storage library"
      generateCode={(values, library) => generateStorageCode(values, library)}
      onSubmit={onSubmit}
      onBack={() => setSelectedSchema(null)}
    />
  );
};
