import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppModeProvider } from "./appMode/AppModeContext";
import { ImportJobProvider } from "./importJob/ImportJobContext";
import { Layout } from "./components/Layout";
import { AddSetPage } from "./pages/AddSetPage";
import { ImportPage } from "./pages/ImportPage";
import { IncompleteSetsReportPage } from "./pages/IncompleteSetsReportPage";
import { MissingPartsReportPage } from "./pages/MissingPartsReportPage";
import { IncompleteCatalogReportPage } from "./pages/IncompleteCatalogReportPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SetDetailPage } from "./pages/SetDetailPage";
import { SetsListPage } from "./pages/SetsListPage";
import { SearchPage } from "./pages/SearchPage";
import { SettingsPage } from "./pages/SettingsPage";
import "./App.css";

export default function App() {
  return (
    <AppModeProvider>
      <ImportJobProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<SetsListPage />} />
            <Route path="sets/:id" element={<SetDetailPage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="add" element={<AddSetPage />} />
            <Route path="import" element={<ImportPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="reports/incomplete" element={<IncompleteSetsReportPage />} />
            <Route path="reports/missing" element={<MissingPartsReportPage />} />
            <Route
              path="reports/incomplete-catalog"
              element={<IncompleteCatalogReportPage />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </ImportJobProvider>
    </AppModeProvider>
  );
}
