import type { AppMode } from "./types";

export interface AppCapabilities {
  canSync: boolean;
  canImport: boolean;
  canAddOrDuplicate: boolean;
  canEditCopyFields: boolean;
  canEditCatalog: boolean;
  canEditQuantities: boolean;
  canEditParts: boolean;
  canDeleteCopy: boolean;
  canEditImages: boolean;
  canToggleInvestigated: boolean;
  canEditMissing: boolean;
  canEditMissingPhotos: boolean;
}

const ALL_EDIT: AppCapabilities = {
  canSync: true,
  canImport: true,
  canAddOrDuplicate: true,
  canEditCopyFields: true,
  canEditCatalog: true,
  canEditQuantities: true,
  canEditParts: true,
  canDeleteCopy: true,
  canEditImages: true,
  canToggleInvestigated: true,
  canEditMissing: true,
  canEditMissingPhotos: true,
};

const VIEW_ONLY: AppCapabilities = {
  canSync: false,
  canImport: false,
  canAddOrDuplicate: false,
  canEditCopyFields: false,
  canEditCatalog: false,
  canEditQuantities: false,
  canEditParts: false,
  canDeleteCopy: false,
  canEditImages: false,
  canToggleInvestigated: false,
  canEditMissing: false,
  canEditMissingPhotos: false,
};

export function getCapabilities(mode: AppMode): AppCapabilities {
  switch (mode) {
    case "edit":
      return ALL_EDIT;
    case "investigate":
      return {
        ...VIEW_ONLY,
        canToggleInvestigated: true,
        canEditMissing: true,
        canEditMissingPhotos: true,
      };
    case "view":
    default:
      return VIEW_ONLY;
  }
}
