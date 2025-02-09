/* Copyright 2024 Marimo. All rights reserved. */
import type { z } from "zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { ZodForm } from "@/components/forms/form";
import {
  type DatabaseConnectionSchema,
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
} from "./schemas";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { DatabaseLogo } from "@/components/databases/icon";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";

interface Props {
  onSubmit: (data: z.infer<typeof DatabaseConnectionSchema>) => void;
}

const SCHEMAS = [
  {
    name: "PostgreSQL",
    schema: PostgresConnectionSchema,
    color: "#336791",
    logo: "postgres",
  },
  {
    name: "MySQL",
    schema: MySQLConnectionSchema,
    color: "#00758F",
    logo: "mysql",
  },
  {
    name: "SQLite",
    schema: SQLiteConnectionSchema,
    color: "#003B57",
    logo: "sqlite",
  },
  {
    name: "DuckDB",
    schema: DuckDBConnectionSchema,
    color: "#FFD700",
    logo: "duckdb",
  },
  {
    name: "Snowflake",
    schema: SnowflakeConnectionSchema,
    color: "#29B5E8",
    logo: "snowflake",
  },
  {
    name: "BigQuery",
    schema: BigQueryConnectionSchema,
    color: "#4285F4",
    logo: "googlebigquery",
  },
];

const DatabaseSchemaSelector: React.FC<{
  onSelect: (schema: z.ZodType) => void;
}> = ({ onSelect }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
      {SCHEMAS.map(({ name, schema, color, logo }) => (
        <Button
          key={name}
          className="h-28 flex flex-col items-center justify-center gap-3 transition-all hover:scale-105 hover:brightness-110"
          style={{ backgroundColor: color }}
          onClick={() => onSelect(schema)}
        >
          <DatabaseLogo
            name={logo}
            className="w-10 h-10 text-white brightness-0 invert dark:invert"
          />
          <span className="text-white font-medium text-lg">{name}</span>
        </Button>
      ))}
    </div>
  );
};

const DatabaseForm: React.FC<{
  schema: z.ZodType;
  onSubmit: (data: z.infer<typeof DatabaseConnectionSchema>) => void;
  onBack: () => void;
}> = ({ schema, onSubmit, onBack }) => {
  const form = useForm<z.infer<typeof DatabaseConnectionSchema>>({
    resolver: zodResolver(schema),
  });

  const errors = form.formState.errors;
  const errorMessage = errors[Object.keys(errors)[0]]?.message;

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      {errorMessage && <ErrorBanner error={errorMessage} />}
      <ZodForm schema={schema} form={form} />
      <div className="flex gap-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="submit" disabled={!form.formState.isValid}>
          Add
        </Button>
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

  const onSubmit = (values: z.infer<typeof DatabaseConnectionSchema>) => {
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild={true}>{children}</DialogTrigger>
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
        <AddDatabaseForm
          onSubmit={(values) => {
            onSubmit(values);
            setOpen(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
};
