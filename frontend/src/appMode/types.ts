export type AppMode = "view" | "investigate" | "edit";

export const APP_MODES: AppMode[] = ["view", "investigate", "edit"];

export const MODE_LABELS: Record<AppMode, string> = {
  view: "View mode",
  investigate: "Investigate mode",
  edit: "Edit mode",
};
