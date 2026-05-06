import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import AppShell from '@/components/layout/AppShell';
import RequireAuth from '@/components/layout/RequireAuth';
import RedirectWithParams from '@/components/routing/RedirectWithParams';
import CitationManualPage from '@/pages/CitationManualPage';
import CitationMonitorPage from '@/pages/CitationMonitorPage';
import ContentBriefDetailPage from '@/pages/ContentBriefDetailPage';
import ContentBriefsPage from '@/pages/ContentBriefsPage';
import DashboardPage from '@/pages/DashboardPage';
import HomePage from '@/pages/HomePage';
import InquiriesPage from '@/pages/InquiriesPage';
import KeywordUniversePage from '@/pages/KeywordUniversePage';
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
            <Route index element={<HomePage />} />

            {/* ===== 新URL構造(5タブ集約) ===== */}
            {/* 分析 */}
            <Route path="analytics" element={<DashboardPage />} />
            <Route path="analytics/citations" element={<CitationMonitorPage />} />
            <Route path="analytics/citations/manual" element={<CitationManualPage />} />

            {/* 戦略 (タブ単独アクセスは summary に飛ばす) */}
            <Route path="strategy" element={<Navigate to="/strategy/summary" replace />} />
            <Route path="strategy/summary" element={<StrategicReviewPage />} />
            <Route path="strategy/universe" element={<KeywordUniversePage />} />
            <Route path="strategy/queries" element={<TargetQueriesPage />} />

            {/* 制作 (タブ単独アクセスは briefs に飛ばす) */}
            <Route path="production" element={<Navigate to="/production/briefs" replace />} />
            <Route path="production/briefs" element={<ContentBriefsPage />} />
            {/* /production/briefs/new はホーム画面のアクションリンクで使われるが、
                Phase C 着手までは KeywordUniverse に飛ばして主軸キーワード選択を促す */}
            <Route
              path="production/briefs/new"
              element={<Navigate to="/strategy/universe" replace />}
            />
            <Route path="production/briefs/:id" element={<ContentBriefDetailPage />} />
            <Route path="production/inquiries" element={<InquiriesPage />} />

            {/* 設定 */}
            <Route path="settings" element={<SettingsPage />} />
            <Route path="settings/manual" element={<ManualPage />} />

            {/* ===== 旧URL → 新URL リダイレクト(6ヶ月互換維持予定) ===== */}
            <Route path="strategic" element={<Navigate to="/strategy/summary" replace />} />
            <Route path="queries" element={<Navigate to="/strategy/queries" replace />} />
            <Route
              path="keyword-universe"
              element={<Navigate to="/strategy/universe" replace />}
            />
            <Route
              path="content-briefs"
              element={<Navigate to="/production/briefs" replace />}
            />
            <Route
              path="content-briefs/:id"
              element={<RedirectWithParams to="/production/briefs/:id" />}
            />
            <Route
              path="citations"
              element={<Navigate to="/analytics/citations" replace />}
            />
            <Route
              path="citations/manual"
              element={<Navigate to="/analytics/citations/manual" replace />}
            />
            <Route
              path="inquiries"
              element={<Navigate to="/production/inquiries" replace />}
            />
            <Route path="manual" element={<Navigate to="/settings/manual" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
