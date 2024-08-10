/* Copyright 2024 Marimo. All rights reserved. */

import { Button } from "../inputs/Inputs";
import { Tooltip } from "../../ui/tooltip";
import { Home } from "lucide-react";

export const HomeButton = () => {
  return (
    <Tooltip content="Home">
      <a href={document.baseURI}>
        <Button
          aria-label="Home"
          data-testid="home-button"
          shape="circle"
          size="small"
          className="h-[27px] w-[27px]"
        >
          <Home size={14} />{" "}
        </Button>
      </a>
    </Tooltip>
  );
};
