/* Copyright 2024 Marimo. All rights reserved. */
import type { z } from "zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { type FormRenderer, ZodForm } from "@/components/forms/form";
import {
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
  type DatabaseConnection,
  ClickhouseConnectionSchema,
  TimeplusConnectionSchema,
  ChdbConnectionSchema,
  TrinoConnectionSchema,
  IcebergConnectionSchema,
  DataFusionConnectionSchema,
  PySparkConnectionSchema,
} from "./schemas";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { DatabaseLogo, type DBLogoName } from "@/components/databases/icon";
import { useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import {
  ConnectionDisplayNames,
  type ConnectionLibrary,
  generateDatabaseCode,
} from "./as-code";
import { FormErrorsBanner } from "@/components/ui/form";
import { getDefaults } from "@/components/forms/form-utils";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ENV_RENDERER, SecretsProvider } from "./form-renderers";
import { ExternalLink } from "@/components/ui/links";

interface Props {
  onSubmit: () => void;
}

interface ConnectionSchema {
  name: string;
  schema: z.ZodType;
  color: string;
  logo: DBLogoName;
  connectionLibraries: {
    libraries: ConnectionLibrary[];
    preferred: ConnectionLibrary;
  };
}

// default to sqlalchemy because it has fewer dependencies
const DATABASES = [
  {
    name: "PostgreSQL",
    schema: PostgresConnectionSchema,
    color: "#336791",
    logo: "postgres",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "MySQL",
    schema: MySQLConnectionSchema,
    color: "#00758F",
    logo: "mysql",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "SQLite",
    schema: SQLiteConnectionSchema,
    color: "#003B57",
    logo: "sqlite",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "DuckDB",
    schema: DuckDBConnectionSchema,
    color: "#FFD700",
    logo: "duckdb",
    connectionLibraries: {
      libraries: ["duckdb"],
      preferred: "duckdb",
    },
  },
  {
    name: "Snowflake",
    schema: SnowflakeConnectionSchema,
    color: "#29B5E8",
    logo: "snowflake",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "ClickHouse",
    schema: ClickhouseConnectionSchema,
    color: "#2C2C1D",
    logo: "clickhouse",
    connectionLibraries: {
      libraries: ["clickhouse_connect"],
      preferred: "clickhouse_connect",
    },
  },
  {
    name: "Timeplus",
    schema: TimeplusConnectionSchema,
    color: "#B83280",
    logo: "timeplus",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "BigQuery",
    schema: BigQueryConnectionSchema,
    color: "#4285F4",
    logo: "bigquery",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "ClickHouse Embedded",
    schema: ChdbConnectionSchema,
    color: "#f2b611",
    logo: "clickhouse",
    connectionLibraries: {
      libraries: ["chdb"],
      preferred: "chdb",
    },
  },
  {
    name: "Trino",
    schema: TrinoConnectionSchema,
    color: "#d466b6",
    logo: "trino",
    connectionLibraries: {
      libraries: ["sqlalchemy", "sqlmodel"],
      preferred: "sqlalchemy",
    },
  },
  {
    name: "DataFusion",
    schema: DataFusionConnectionSchema,
    color: "#202A37",
    logo: "datafusion",
    connectionLibraries: {
      libraries: ["ibis"],
      preferred: "ibis",
    },
  },
  {
    name: "PySpark",
    schema: PySparkConnectionSchema,
    color: "#1C5162",
    logo: "pyspark",
    connectionLibraries: {
      libraries: ["ibis"],
      preferred: "ibis",
    },
  },
] satisfies ConnectionSchema[];

const DATA_CATALOGS = [
  {
    name: "Iceberg",
    schema: IcebergConnectionSchema,
    color: "#000000",
    logo: "iceberg",
    connectionLibraries: {
      libraries: ["pyiceberg"],
      preferred: "pyiceberg",
    },
  },
] satisfies ConnectionSchema[];

const DatabaseSchemaSelector: React.FC<{
  onSelect: (schema: z.ZodType) => void;
}> = ({ onSelect }) => {
  const renderItem = ({ name, schema, color, logo }: ConnectionSchema) => {
    return (
      <button
        type="button"
        key={name}
        className="py-3 flex flex-col items-center justify-center gap-1 transition-all hover:scale-105 hover:brightness-110 rounded shadow-smSolid hover:shadow-mdSolid"
        style={{ backgroundColor: color }}
        onClick={() => onSelect(schema)}
      >
        <DatabaseLogo
          name={logo}
          className="w-8 h-8 text-white brightness-0 invert dark:invert"
        />
        <span className="text-white font-medium text-lg">{name}</span>
      </button>
    );
  };

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {DATABASES.map(renderItem)}
      </div>
      <h4 className="font-semibold text-muted-foreground text-lg flex items-center gap-4">
        Data Catalogs
        <hr className="flex-1" />
      </h4>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {DATA_CATALOGS.map(renderItem)}
      </div>
    </>
  );
};

const RENDERERS: FormRenderer[] = [ENV_RENDERER];

const DatabaseForm: React.FC<{
  schema: z.ZodType;
  onSubmit: () => void;
  onBack: () => void;
}> = ({ schema, onSubmit, onBack }) => {
  const form = useForm<DatabaseConnection>({
    defaultValues: getDefaults(schema),
    resolver: zodResolver(schema),
    reValidateMode: "onChange",
  });

  const connectionLibraries = [...DATABASES, ...DATA_CATALOGS].find(
    (s) => s.schema === schema,
  )?.connectionLibraries;
  const [preferredConnection, setPreferredConnection] =
    useState<ConnectionLibrary>(connectionLibraries?.preferred ?? "sqlalchemy");

  const { createNewCell } = useCellActions();
  const lastFocusedCellId = useLastFocusedCellId();

  const handleInsertCode = (code: string) => {
    createNewCell({
      code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
      skipIfCodeExists: true,
      autoFocus: true,
    });
  };

  const handleSubmit = (values: DatabaseConnection) => {
    handleInsertCode(generateDatabaseCode(values, preferredConnection));
    onSubmit();
  };

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
      <SecretsProvider>
        <ZodForm schema={schema} form={form} renderers={RENDERERS}>
          <FormErrorsBanner />
        </ZodForm>
      </SecretsProvider>
      <div className="flex gap-2 justify-between">
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button type="submit" disabled={!form.formState.isValid}>
            Add
          </Button>
        </div>
        <div>
          <Select
            value={preferredConnection}
            onValueChange={(value) =>
              setPreferredConnection(value as ConnectionLibrary)
            }
          >
            <div className="flex flex-col gap-1 items-end">
              <SelectTrigger>
                <SelectValue placeholder="Select a library" />
              </SelectTrigger>
              <span className="text-xs text-muted-foreground">
                Preferred connection library
              </span>
            </div>
            <SelectContent>
              <SelectGroup>
                {connectionLibraries?.libraries.map((library) => (
                  <SelectItem key={library} value={library}>
                    {ConnectionDisplayNames[library]}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </div>
    </form>
  );
};

const AddDatabaseForm: React.FC<Props> = ({ onSubmit }) => {
  const [selectedSchema, setSelectedSchema] = useState<z.ZodType | null>(null);

  if (!selectedSchema) {
    return <DatabaseSchemaSelector onSelect={setSelectedSchema} />;
  }

  return (
    <DatabaseForm
      schema={selectedSchema}
      onSubmit={onSubmit}
      onBack={() => setSelectedSchema(null)}
    />
  );
};

export const AddDatabaseDialog: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild={true}>{children}</DialogTrigger>
      <AddDatabaseDialogContent onClose={() => setOpen(false)} />
    </Dialog>
  );
};

export const AddDatabaseDialogContent: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  return (
    <DialogContent className="max-h-[75vh] overflow-y-auto">
      <DialogHeader className="mb-4">
        <DialogTitle>Add Connection</DialogTitle>
        <DialogDescription>
          Connect to your database or data catalog to query data directly from
          your notebook. Learn more about how to connect to your database in our{" "}
          <ExternalLink href="https://docs.marimo.io/guides/working_with_data/sql/#connecting-to-a-custom-database">
            docs.
          </ExternalLink>
        </DialogDescription>
      </DialogHeader>
      <AddDatabaseForm onSubmit={() => onClose()} />
    </DialogContent>
  );
};
