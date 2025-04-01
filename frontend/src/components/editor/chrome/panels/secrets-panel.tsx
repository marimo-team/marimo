/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { KeyIcon, PlusIcon } from "lucide-react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Spinner } from "@/components/icons/spinner";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { PanelEmptyState } from "./empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/use-toast";
import { copyToClipboard } from "@/utils/copy";
import { cn } from "@/utils/cn";
import { SECRETS_REGISTRY } from "@/core/secrets/request-registry";
import { Badge } from "@/components/ui/badge";
import type { ListSecretKeysResponse } from "@/core/network/types";
import { Button } from "@/components/ui/button";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { writeSecret } from "@/core/network/requests";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormDescription } from "@/components/ui/field";
import { ExternalLink } from "@/components/ui/links";

// dotenv providers should be at the top
function sortProviders(providers: ListSecretKeysResponse["keys"]) {
  return providers.sort((a, b) => {
    if (a.provider === "env") {
      return 1;
    }
    if (b.provider === "env") {
      return -1;
    }
    return 0;
  });
}

const WriteSecretModal: React.FC<{
  providerNames: string[];
  onClose: () => void;
  onSuccess: () => void;
}> = ({ providerNames, onClose, onSuccess }) => {
  const [key, setKey] = React.useState("");
  const [value, setValue] = React.useState("");
  const [location, setLocation] = React.useState(providerNames[0] || ".env");
  // Only dotenv is supported for now
  const provider = "dotenv";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await writeSecret({
        key,
        value,
        provider,
        name: location,
      });
      toast({
        title: "Secret created",
        description: "The secret has been created successfully.",
      });
      onSuccess();
    } catch {
      toast({
        title: "Error",
        description: "Failed to create secret. Please try again.",
        variant: "danger",
      });
    }
  };

  return (
    <DialogContent>
      <form onSubmit={handleSubmit}>
        <DialogHeader>
          <DialogTitle>Add Secret</DialogTitle>
          <DialogDescription>
            Add a new secret to your environment variables.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="key">Key</Label>
            <Input
              id="key"
              value={key}
              onChange={(e) => {
                // Remove any whitespace from the input
                setKey(e.target.value.replaceAll(/\s+/g, "_"));
              }}
              placeholder="MY_SECRET_KEY"
              required={true}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="value">Value</Label>
            <Input
              id="value"
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required={true}
              autoComplete="off"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="location">Location</Label>
            <Select
              value={location}
              onValueChange={(value) => setLocation(value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a provider" />
              </SelectTrigger>
              <SelectContent>
                {providerNames.map((name) => (
                  <SelectItem key={name} value={name}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FormDescription>
              You can configure the location by setting the{" "}
              <ExternalLink href="https://links.marimo.app/dotenv">
                dotenv configuration
              </ExternalLink>
              .
            </FormDescription>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit">Add Secret</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
};

export const SecretsPanel: React.FC = () => {
  const { openModal, closeModal } = useImperativeModal();
  const {
    data: secretKeyProviders = [],
    loading,
    error,
    reload,
  } = useAsyncData(async () => {
    const result = await SECRETS_REGISTRY.request({});
    return sortProviders(result.secrets);
  }, []);

  // Provider names without 'env' provider
  const providerNames = secretKeyProviders
    .filter((provider) => provider.provider !== "env")
    .map((provider) => provider.name);

  // Only show on the first load
  if (loading && secretKeyProviders.length === 0) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (secretKeyProviders.length === 0) {
    return (
      <PanelEmptyState
        title="No environment variables"
        description="No environment variables are available in this notebook."
        icon={<KeyIcon />}
      />
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-end h-8 border-b">
        <button
          type="button"
          className="float-right border-l px-2 m-0 h-full hover:bg-accent hover:text-accent-foreground"
          onClick={() =>
            openModal(
              <WriteSecretModal
                providerNames={providerNames}
                onSuccess={() => {
                  reload();
                  closeModal();
                }}
                onClose={closeModal}
              />,
            )
          }
        >
          <PlusIcon className="h-4 w-4" />
        </button>
      </div>
      <Table className="overflow-auto flex-1">
        <TableHeader>
          <TableRow>
            <TableHead>Environment Variable</TableHead>
            <TableHead>Source</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {secretKeyProviders.map((provider) => {
            return provider.keys.map((key) => (
              <TableRow key={`${provider.name}-${key}`} className="group">
                <TableCell>{key}</TableCell>
                <TableCell>
                  {provider.provider !== "env" && (
                    <Badge variant="outline" className="select-none">
                      {provider.name}
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <button
                    type="button"
                    onClick={async () => {
                      await copyToClipboard(`os.environ["${key}"]`);
                      toast({
                        title: "Copied to clipboard",
                        description: `os.environ["${key}"] has been copied to your clipboard.`,
                      });
                    }}
                    className={cn(
                      "float-right px-2 h-full text-xs text-muted-foreground hover:text-foreground",
                      "invisible group-hover:visible",
                    )}
                  >
                    Copy
                  </button>
                </TableCell>
              </TableRow>
            ));
          })}
        </TableBody>
      </Table>
    </div>
  );
};
