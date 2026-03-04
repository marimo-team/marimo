/* Copyright 2026 Marimo. All rights reserved. */

import AwsIcon from "@marimo-team/llm-info/icons/aws.svg?inline";
import AwsDarkIcon from "@marimo-team/llm-info/icons/aws-dark.svg?inline";
import AzureIcon from "@marimo-team/llm-info/icons/azure.svg?inline";
import CloudflareIcon from "@marimo-team/llm-info/icons/cloudflare.svg?inline";
import CoreweaveIcon from "@marimo-team/llm-info/icons/coreweave.svg?inline";
import CoreweaveDarkIcon from "@marimo-team/llm-info/icons/coreweave-dark.svg?inline";
import {
  DatabaseZapIcon,
  GithubIcon,
  GlobeIcon,
  HardDriveIcon,
} from "lucide-react";
import GoogleCloudIcon from "@/components/databases/icons/google-cloud-storage.svg?inline";
import GoogleDriveIcon from "@/components/databases/icons/google-drive.svg?inline";
import type { KnownStorageProtocol } from "@/core/storage/types";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";

type IconEntry =
  | { src: string; dark?: string }
  | React.ComponentType<{ className?: string }>;

const PROTOCOL_ICONS: Record<KnownStorageProtocol, IconEntry> = {
  s3: { src: AwsIcon, dark: AwsDarkIcon },
  coreweave: { src: CoreweaveIcon, dark: CoreweaveDarkIcon },
  cloudflare: { src: CloudflareIcon },
  azure: { src: AzureIcon },
  gcs: { src: GoogleCloudIcon },
  http: GlobeIcon,
  file: HardDriveIcon,
  "in-memory": DatabaseZapIcon,
  gdrive: { src: GoogleDriveIcon },
  github: GithubIcon,
};

export const ProtocolIcon: React.FC<{
  protocol: KnownStorageProtocol | (string & {});
  className?: string;
}> = ({ protocol, className }) => {
  const { theme } = useTheme();
  const entry =
    PROTOCOL_ICONS[protocol.toLowerCase() as KnownStorageProtocol] ??
    HardDriveIcon;

  if ("src" in entry) {
    const src = theme === "dark" && entry.dark ? entry.dark : entry.src;
    return (
      <img src={src} alt={protocol} className={cn("h-3.5 w-3.5", className)} />
    );
  }

  const Icon = entry;
  return <Icon className={cn("h-3.5 w-3.5", className)} />;
};
