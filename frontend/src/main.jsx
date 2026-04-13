import { Suspense, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@gcds-core/components-react/gcds.css";
import "@gcds-core/css-shortcuts/dist/gcds-css-shortcuts.min.css";
import "./index.css";
import router from "./router";
import { RouterProvider } from "react-router";
import ReactGA from "react-ga4";

import config from "./config.jsx";

if (config.gatag) {
  ReactGA.initialize(config.gatag, {
    gaOptions: {
      anonymize_ip: true,
    },
  });
}
try {
  createRoot(document.getElementById("root")).render(
    <StrictMode>
      <Suspense fallback={null}>
        <RouterProvider router={router} />
      </Suspense>
    </StrictMode>,
  );
  console.log("React application rendered successfully"); // Debug log
} catch (error) {
  console.error("Error rendering React application:", error);
}
