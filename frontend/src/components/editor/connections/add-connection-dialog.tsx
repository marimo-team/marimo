/* Copyright 2026 Marimo. All rights reserved. */

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ExternalLink } from "@/components/ui/links";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AddDatabaseForm } from "./database/add-database-form";
import { AddStorageForm } from "./storage/add-storage-form";

type ConnectionTab = "databases" | "storage";

export const AddConnectionDialog: React.FC<{
  children: React.ReactNode;
  defaultTab?: ConnectionTab;
}> = ({ children, defaultTab = "databases" }) => {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild={true}>{children}</DialogTrigger>
      <AddConnectionDialogContent
        defaultTab={defaultTab}
        onClose={() => setOpen(false)}
      />
    </Dialog>
  );
};

export const AddConnectionDialogContent: React.FC<{
  defaultTab?: ConnectionTab;
  onClose: () => void;
}> = ({ defaultTab = "databases", onClose }) => {
  const [activeTab, setActiveTab] = useState<ConnectionTab>(defaultTab);

  const tabHeader = (
    <TabsList className="w-full mb-4">
      <TabsTrigger value="databases" className="flex-1">
        Databases & Catalogs
      </TabsTrigger>
      <TabsTrigger value="storage" className="flex-1">
        Remote Storages
      </TabsTrigger>
    </TabsList>
  );

  const codeSnippetHint =
    activeTab === "databases" ? (
      <>
        Don't see your database or connection method? A{" "}
        <ExternalLink href="https://docs.marimo.io/guides/working_with_data/sql/#connecting-to-a-custom-database">
          code snippet
        </ExternalLink>{" "}
        is all you need.
      </>
    ) : (
      <>
        Don't see your storage or connection method? A{" "}
        <ExternalLink href="https://docs.marimo.io/guides/working_with_data/remote_storage/">
          code snippet
        </ExternalLink>{" "}
        is all you need.
      </>
    );

  return (
    <DialogContent className="max-h-[75vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Add Connection</DialogTitle>
        <DialogDescription>
          Connect to a{" "}
          <ExternalLink href="https://docs.marimo.io/guides/working_with_data/sql/#connecting-to-a-custom-database">
            database, data catalog
          </ExternalLink>{" "}
          or{" "}
          <ExternalLink href="https://docs.marimo.io/guides/working_with_data/remote_storage/">
            remote storage
          </ExternalLink>{" "}
          directly from your notebook.
          <p>{codeSnippetHint}</p>
        </DialogDescription>
      </DialogHeader>
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as ConnectionTab)}
      >
        <TabsContent
          value="databases"
          className="mt-0 focus-visible:ring-0 focus-visible:ring-offset-0"
        >
          <AddDatabaseForm onSubmit={onClose} header={tabHeader} />
        </TabsContent>
        <TabsContent
          value="storage"
          className="mt-0 focus-visible:ring-0 focus-visible:ring-offset-0"
        >
          <AddStorageForm onSubmit={onClose} header={tabHeader} />
        </TabsContent>
      </Tabs>
    </DialogContent>
  );
};
