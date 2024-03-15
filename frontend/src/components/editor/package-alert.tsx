/* Copyright 2024 Marimo. All rights reserved. */
import { usePackageAlert, usePackageAlertActions } from "@/core/alerts/state";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { Banner } from "@/plugins/impl/common/error-banner";
import { PackageXIcon, BoxIcon, AlertCircleIcon, DownloadCloudIcon, XIcon } from "lucide-react";
import React from "react";
import { Button } from "../ui/button";
//import { useRestartKernel } from "./actions/useRestartKernel";

// TODO On install click, installation alert removed and instead we render installation progress ...
// - check mark if package installation succeeded
// - packageXIcon if failed
// - installation logs stay in terminal for now ... TODO to route to frontend
export const PackageAlert: React.FC = (props) => {
  const { alert } = usePackageAlert();
  const { clearAlert } = usePackageAlertActions();

  if (alert === null) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200]">
      <Banner kind="danger" className="flex flex-col rounded py-3 px-5">
        <div className="flex justify-between">
          <span className="font-bold text-lg flex items-center mb-2">
            <PackageXIcon className="w-5 h-5 inline-block mr-2" />
            Missing packages
          </span>
          <Button variant="text" size="icon" onClick={() => clearAlert()}>
            <XIcon className="w-5 h-5" />
          </Button>
        </div>
        <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground">
          <div>
            <p>The following modules were not found:</p>
            <ul className="list-disc ml-4 mt-1">
              {alert.packages.map((pkg) => (
                <li className="flex items-center gap-1 font-mono"><BoxIcon size="1rem"/>{pkg}</li>
              ))}
            </ul>
          </div>
          <div className="ml-auto">
            <InstallPackagesButton />
          </div>
        </div>
      </Banner>
    </div>
  );
};

const InstallPackagesButton = () => {
  //const restartKernel = useRestartKernel();
  return (
    //<Button variant="outline" size="sm" onClick={restartKernel}>
    <Button variant="outline" size="sm">
      <DownloadCloudIcon className="w-4 h-4 mr-2" />
      <span className="font-semibold">Install with pip</span>
    </Button>
  );
};
