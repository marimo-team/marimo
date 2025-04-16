/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { toast } from "@/components/ui/use-toast";
import { Button } from "@/components/ui/button";
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
import type { ListSecretKeysResponse } from "@/core/network/types";

// dotenv providers should be at the top
export function sortProviders(providers: ListSecretKeysResponse["keys"]) {
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

/**
 * A modal component that allows users to add a new secret
 */
export const WriteSecretModal: React.FC<{
  providerNames: string[];
  onClose: () => void;
  onSuccess: (secretName: string) => void;
}> = ({ providerNames, onClose, onSuccess }) => {
  const [key, setKey] = React.useState("");
  const [value, setValue] = React.useState("");
  const [location, setLocation] = React.useState<string | undefined>(
    providerNames[0],
  );
  // Only dotenv is supported for now
  const provider = "dotenv";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!location) {
      toast({
        title: "Error",
        description: "No location selected for the secret.",
        variant: "danger",
      });
      return;
    }

    if (!key || !value || !location) {
      toast({
        title: "Error",
        description: "Please fill in all fields.",
        variant: "danger",
      });
      return;
    }

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
      onSuccess(key);
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
            {providerNames.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No dotenv locations configured.
              </p>
            )}
            {providerNames.length > 0 && (
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
            )}
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
          <Button type="submit" disabled={!key || !value || !location}>
            Add Secret
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
};
