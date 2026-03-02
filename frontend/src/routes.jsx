import { Navigate } from "react-router";

import RootLayout from "./components/Layout/RootLayout.jsx";
import { AppLanguageSetup } from "./components/Providers/AppLanguageSetup";
import { LanguageProvider } from "./components/Providers/LanguageProvider";
import { PrivateRoute } from "./components/Providers/PrivateRoute.jsx";
import { UserProvider } from "./components/Providers/UserProvider";

import SkipLink from "./features/DoubleSignIn/components/SkipLink.jsx";
import LinkPrompt from "./features/DoubleSignIn/components/LinkPrompt.jsx";
import LinkSuccess from "./features/DoubleSignIn/components/LinkSuccess.jsx";
import LegacyLanguageSync from "./features/DoubleSignIn/components/LegacyLanguageSync.jsx";
import { PAGES } from "./utils/constants.jsx";

export const appRoutes = [
  {
    element: (
      <UserProvider>
        <LanguageProvider>
          <AppLanguageSetup />
          <PrivateRoute />
        </LanguageProvider>
      </UserProvider>
    ),
    children: [
      {
        path: "/:language/link/lang-sync",
        element: <LegacyLanguageSync />,
      },
      {
        element: <RootLayout />,
        children: [
          {
            path: "/",
            element: <Navigate to="/en/link" replace />,
          },
          {
            path: "/:language",
            children: [
              {
                index: true,
                element: <Navigate to="link" replace />,
              },
              {
                path: "link",
                handle: { id: PAGES.LinkPrompt },
                children: [
                  {
                    index: true,
                    element: <LinkPrompt />,
                  },
                  {
                    path: "skip",
                    element: <SkipLink />,
                    handle: { id: PAGES.SkipLink },
                  },
                  {
                    path: "success",
                    element: <LinkSuccess />,
                    handle: { id: PAGES.LinkSuccess },
                  },
                ],
              },
              {
                path: "*",
                element: <Navigate to="../link" replace />,
              },
            ],
          },
          { path: "*", element: <Navigate to="/en/link" replace /> },
        ],
      },
    ],
  },
];
