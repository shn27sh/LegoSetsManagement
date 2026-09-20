import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getCapabilities, type AppCapabilities } from "./capabilities";
import { ensureEditAccess } from "./editAccess";
import { readStoredAppMode, writeStoredAppMode } from "./storage";
import { MODE_LABELS, type AppMode } from "./types";

interface AppModeContextValue {
  mode: AppMode;
  modeLabel: string;
  capabilities: AppCapabilities;
  setMode: (mode: AppMode) => Promise<boolean>;
}

const AppModeContext = createContext<AppModeContextValue | null>(null);

interface AppModeProviderProps {
  children: ReactNode;
  /** Test override; skips localStorage on first render. */
  initialMode?: AppMode;
}

export function AppModeProvider({
  children,
  initialMode,
}: AppModeProviderProps) {
  const [mode, setModeState] = useState<AppMode>(
    () => initialMode ?? readStoredAppMode(),
  );

  const setMode = useCallback(async (next: AppMode): Promise<boolean> => {
    if (next === "edit") {
      const allowed = await ensureEditAccess();
      if (!allowed) {
        return false;
      }
    }
    setModeState(next);
    writeStoredAppMode(next);
    return true;
  }, []);

  const value = useMemo(
    (): AppModeContextValue => ({
      mode,
      modeLabel: MODE_LABELS[mode],
      capabilities: getCapabilities(mode),
      setMode,
    }),
    [mode, setMode],
  );

  return (
    <AppModeContext.Provider value={value}>{children}</AppModeContext.Provider>
  );
}

export function useAppMode(): AppModeContextValue {
  const ctx = useContext(AppModeContext);
  if (ctx == null) {
    throw new Error("useAppMode must be used within AppModeProvider");
  }
  return ctx;
}

export function useCapabilities(): AppCapabilities {
  return useAppMode().capabilities;
}
