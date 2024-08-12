import { initializePlugins } from "@/plugins/plugins";
import { initializeIslands } from "./initialize";

// This will display all the static HTML content.
initializePlugins();
// This will initialize the <marimo-island> elements.
void initializeIslands({}).catch((error) => {
  console.error(error);
});
