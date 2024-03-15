/* Copyright 2024 Marimo. All rights reserved. */
import { PackageInstallationStatus } from "@/core/kernel/messages";
import {
  useAlerts,
  useAlertActions,
  isMissingPackageAlert,
  isInstallingPackageAlert,
} from "@/core/alerts/state";
import { logNever } from "@/utils/assertNever";
import { Banner } from "@/plugins/impl/common/error-banner";
import { PackageXIcon, BoxIcon, DownloadCloudIcon, XIcon } from "lucide-react";
import React from "react";
import { Button } from "../ui/button";
//import { useRestartKernel } from "./actions/useRestartKernel";

// TODO On install click, installation alert removed and instead we render installation progress ...
// - check mark if package installation succeeded
// - packageXIcon if failed
// - installation logs stay in terminal for now ... TODO to route to frontend
export const PackageAlert: React.FC = (props) => {
  const { packageAlert } = useAlerts();
  const { addPackageAlert, clearPackageAlert } = useAlertActions();

  if (packageAlert === null) {
    return null;
  }

  if (isMissingPackageAlert(packageAlert)) {
    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200]">
        <Banner kind="danger" className="flex flex-col rounded py-3 px-5">
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              <PackageXIcon className="w-5 h-5 inline-block mr-2" />
              Missing packages
            </span>
            <Button
              variant="text"
              size="icon"
              onClick={() => clearPackageAlert()}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground">
            <div>
              <p>The following modules were not found:</p>
              <ul className="list-disc ml-4 mt-1">
                {packageAlert.packages.map((pkg) => (
                  <li className="flex items-center gap-1 font-mono">
                    <BoxIcon size="1rem" />
                    {pkg}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ml-auto">
              <InstallPackagesButton
                packages={packageAlert.packages}
                addPackageAlert={addPackageAlert}
              />
            </div>
          </div>
        </Banner>
      </div>
    );
  } else if (isInstallingPackageAlert(packageAlert)) {
    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200]">
        <Banner kind="info" className="flex flex-col rounded py-3 px-5">
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              <PackageXIcon className="w-5 h-5 inline-block mr-2" />
              Installing packages ... Hang tight!
            </span>
            <Button
              variant="text"
              size="icon"
              onClick={() => clearPackageAlert()}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground">
            <div>
              <p>The following modules were not found:</p>
              <ul className="list-disc ml-4 mt-1">
                {packageAlert.packages.map((pkg) => (
                  <li className="flex items-center gap-1 font-mono">
                    <BoxIcon size="1rem" />
                    {pkg.name}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Banner>
      </div>
    );
  } else {
    logNever(packageAlert);
    return null;
  }
};

function installPackages(packages: string[], addPackageAlert: any) {
  const packageStatus = packages.map((pkg) => {
    return { name: pkg, status: "queued" };
  }) as PackageInstallationStatus;
  addPackageAlert({
    kind: "installing",
    packages: packageStatus,
  });
  // TODO: send package install request
}

const InstallPackagesButton = ({
  packages,
  addPackageAlert,
}: {
  packages: string[];
  addPackageAlert: any;
}) => {
  //const restartKernel = useRestartKernel();
  return (
    //<Button variant="outline" size="sm" onClick={restartKernel}>
    <Button
      variant="outline"
      size="sm"
      onClick={() => installPackages(packages, addPackageAlert)}
    >
      <DownloadCloudIcon className="w-4 h-4 mr-2" />
      <span className="font-semibold">Install with pip</span>
    </Button>
  );
};
