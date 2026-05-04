import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import AppShell from '@/components/layout/AppShell';
import RequireAuth from '@/components/layout/RequireAuth';
import CitationManualPage from '@/pages/CitationManualPage';
import CitationMonitorPage from '@/pages/CitationMonitorPage';
import DashboardPage from '@/pages/DashboardPage';
import InquiriesPage from '@/pages/InquiriesPage';
import LoginPage from '@/pages/LoginPage';
import ManualPage from '@/pages/ManualPage';
import PublicReportPage from '@/pages/PublicReportPage';
import SettingsPage from '@/pages/SettingsPage';
import StrategicReviewPage from '@/pages/StrategicReviewPage';
import TargetQueriesPage from '@/pages/TargetQueriesPage';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/marketer/">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/public/reports/:token" element={<PublicReportPage />} />
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="strategic" element={<StrategicReviewPage />} />
            <Route path="queries" element={<TargetQueriesPage />} />
            <Route path="citations" element={<CitationMonitorPage />} />
            <Route path="citations/manual" element={<CitationManualPage />} />
            <Route path="inquiries" element={<InquiriesPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="manual" element={<ManualPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
