import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AppProvider } from "./state/AppContext";
import { ChatPage } from "./pages/ChatPage";
import { LabelsPage } from "./pages/LabelsPage";
import { LlmSettingsPage } from "./pages/LlmSettingsPage";
import { GraphPage } from "./pages/GraphPage";
import { OpsPage } from "./pages/OpsPage";

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<ChatPage />} />
            <Route path="labels" element={<LabelsPage />} />
            <Route path="llm" element={<LlmSettingsPage />} />
            <Route path="graph" element={<GraphPage />} />
            <Route path="ops" element={<OpsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
