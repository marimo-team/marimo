/* Copyright 2024 Marimo. All rights reserved. */
import type { z } from "zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { ZodForm } from "@/components/forms/form";
import {
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
  type DatabaseConnection,
  ClickhouseConnectionSchema,
  ChdbConnectionSchema,
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

interface Props {
  onSubmit: () => void;
}

// default to sqlalchemy because it has fewer dependencies
const SCHEMAS = [
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
] satisfies Array<{
  name: string;
  schema: z.ZodType;
  color: string;
  logo: DBLogoName;
  connectionLibraries: {
    libraries: ConnectionLibrary[];
    preferred: ConnectionLibrary;
  };
}>;

const DatabaseSchemaSelector: React.FC<{
  onSelect: (schema: z.ZodType) => void;
}> = ({ onSelect }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
      {SCHEMAS.map(({ name, schema, color, logo }) => (
        <button
          type="button"
          key={name}
          className="h-28 flex flex-col items-center justify-center gap-3 transition-all hover:scale-105 hover:brightness-110 rounded shadow-smSolid hover:shadow-mdSolid"
          style={{ backgroundColor: color }}
          onClick={() => onSelect(schema)}
        >
          <DatabaseLogo
            name={logo}
            className="w-10 h-10 text-white brightness-0 invert dark:invert"
          />
          <span className="text-white font-medium text-lg">{name}</span>
        </button>
      ))}
    </div>
  );
};

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

  const connectionLibraries = SCHEMAS.find(
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
      <ZodForm schema={schema} form={form} renderers={undefined}>
        <FormErrorsBanner />
      </ZodForm>
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
    <DialogContent>
      <DialogHeader className="mb-4">
        <DialogTitle>Add Database Connection</DialogTitle>
        <DialogDescription>
          Connect to your database to query data directly from your notebook.
          Learn more about how to connect to your database in our{" "}
          <a
            href="http://docs.marimo.io/guides/working_with_data/sql/#connecting-to-a-custom-database"
            target="_blank"
            rel="noreferrer"
            className="text-link hover:underline"
          >
            docs.
          </a>
        </DialogDescription>
      </DialogHeader>
      <AddDatabaseForm onSubmit={() => onClose()} />
    </DialogContent>
  );
};
