/* Copyright 2024 Marimo. All rights reserved. */
import type { AppConfig } from "@/core/config/config-schema";
import { RunApp } from "@/core/run-app";
import { StaticBanner } from "../static-html/static-banner";

interface Props {
  appConfig: AppConfig;
}

const RunPage = (props: Props) => {
  return (
    <>
      <StaticBanner />
      <RunApp appConfig={props.appConfig} />
    </>
  );
};

export default RunPage;
