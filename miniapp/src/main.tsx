import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root") as HTMLElement, {
  onUncaughtError: (error) => {
    console.log(
      "UNCAUGHT_RENDER_ERROR: " + (error instanceof Error ? `${error.stack}` : String(error)),
    );
  },
}).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
