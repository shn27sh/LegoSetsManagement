import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";
import type { ReactElement, ReactNode } from "react";

import { AppModeProvider } from "../appMode/AppModeContext";
import { ImportJobProvider } from "../importJob/ImportJobContext";
import type { AppMode } from "../appMode/types";

interface RenderWithAppModeOptions extends Omit<RenderOptions, "wrapper"> {
  mode?: AppMode;
  routerProps?: MemoryRouterProps;
}

export function renderWithAppMode(
  ui: ReactElement,
  { mode = "edit", routerProps, ...renderOptions }: RenderWithAppModeOptions = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <AppModeProvider initialMode={mode}>
        <ImportJobProvider>
          <MemoryRouter {...routerProps}>{children}</MemoryRouter>
        </ImportJobProvider>
      </AppModeProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}
