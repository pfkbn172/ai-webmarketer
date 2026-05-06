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
import AnalyticsLayout from '@/pages/analytics/AnalyticsLayout';
import QualityPlaceholder from '@/pages/analytics/QualityPlaceholder';
import RankPlaceholder from '@/pages/analytics/RankPlaceholder';
import ProductionLayout from '@/pages/production/ProductionLayout';
import AuthorsTab from '@/pages/settings/AuthorsTab';
import BusinessContextTab from '@/pages/settings/BusinessContextTab';
import CompetitorsTab from '@/pages/settings/CompetitorsTab';
import CredentialsTab from '@/pages/settings/CredentialsTab';
import OnboardingTab from '@/pages/settings/OnboardingTab';
import SettingsLayout from '@/pages/settings/SettingsLayout';
import SystemStatusTab from '@/pages/settings/SystemStatusTab';
import StrategyLayout from '@/pages/strategy/StrategyLayout';
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
            {/* 分析 — タブシェル(集客/引用率/検索順位/サイト品質)で包む */}
            <Route path="analytics" element={<AnalyticsLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="citations" element={<CitationMonitorPage />} />
              <Route path="citations/manual" element={<CitationManualPage />} />
              <Route path="rank" element={<RankPlaceholder />} />
              <Route path="quality" element={<QualityPlaceholder />} />
            </Route>

            {/* 戦略 — タブシェル(戦略サマリー/ユニバース/クエリ管理)で包む */}
            <Route path="strategy" element={<StrategyLayout />}>
              <Route index element={<Navigate to="/strategy/summary" replace />} />
              <Route path="summary" element={<StrategicReviewPage />} />
              <Route path="universe" element={<KeywordUniversePage />} />
              <Route path="queries" element={<TargetQueriesPage />} />
            </Route>

            {/* 制作 — タブシェル(ブリーフ/問い合わせ)で包む */}
            <Route path="production" element={<ProductionLayout />}>
              <Route index element={<Navigate to="/production/briefs" replace />} />
              <Route path="briefs" element={<ContentBriefsPage />} />
              {/* /production/briefs/new はホーム画面のアクションリンクで使われるが、
                  ウィザードは Phase C-3 のスコープ外。当面は KeywordUniverse に飛ばす */}
              <Route
                path="briefs/new"
                element={<Navigate to="/strategy/universe" replace />}
              />
              <Route path="briefs/:id" element={<ContentBriefDetailPage />} />
              <Route path="inquiries" element={<InquiriesPage />} />
            </Route>

            {/* 設定 — タブシェル(事業情報/認証/競合/著者/状態/マニュアル/オンボーディング)で包む */}
            <Route path="settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="/settings/business" replace />} />
              <Route path="business" element={<BusinessContextTab />} />
              <Route path="credentials" element={<CredentialsTab />} />
              <Route path="competitors" element={<CompetitorsTab />} />
              <Route path="authors" element={<AuthorsTab />} />
              <Route path="status" element={<SystemStatusTab />} />
              <Route path="manual" element={<ManualPage />} />
              <Route path="onboarding" element={<OnboardingTab />} />
            </Route>
            {/* 旧 SettingsPage(カードで Tabs 表示)は廃止。ルートだけ残してリダイレクト */}
            <Route path="settings-legacy" element={<SettingsPage />} />

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
