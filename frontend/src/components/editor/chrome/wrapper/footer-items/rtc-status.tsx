/* Copyright 2024 Marimo. All rights reserved. */

import { connectedDocAtom } from "@/core/codemirror/rtc/extension";
import { useAtomValue, useAtom } from "jotai";
import { UsersIcon } from "lucide-react";
import type React from "react";
import { FooterItem } from "../footer-item";
import { getFeatureFlag } from "@/core/config/feature-flag";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { usernameAtom } from "@/core/rtc/state";

export const RTCStatus: React.FC = () => {
  const connectedDoc = useAtomValue(connectedDocAtom);
  const [username, setUsername] = useAtom(usernameAtom);
  const [open, setOpen] = useState(false);

  if (!getFeatureFlag("rtc_v2")) {
    return null;
  }

  if (connectedDoc === "disabled") {
    return null;
  }

  const tooltip = connectedDoc
    ? "Real-time collaboration active"
    : "Connecting to real-time collaboration";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild={true}>
        <FooterItem tooltip={tooltip} selected={false}>
          <UsersIcon className="w-4 h-4" />
        </FooterItem>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <div className="space-y-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none">Username</h4>
            <p className="text-sm text-muted-foreground">
              Set your username for real-time collaboration
            </p>
          </div>
          <Input
            value={username}
            autoCapitalize="off"
            autoComplete="off"
            autoCorrect="off"
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter your username"
          />
        </div>
      </PopoverContent>
    </Popover>
  );
};
