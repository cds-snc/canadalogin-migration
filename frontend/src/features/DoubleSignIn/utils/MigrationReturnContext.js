import { createContext } from "react";

export const MigrationReturnContext = createContext({
  checking: false,
  resumeVersion: 0,
  canActivate: () => true,
});
