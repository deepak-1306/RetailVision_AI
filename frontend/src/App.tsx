import React, { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import UploadPage from "@/pages/UploadPage";
import LiveStreamPage from "@/pages/LiveStreamPage";
import ProcessingPage from "@/pages/ProcessingPage";
import TimelinePage from "@/pages/TimelinePage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import PurchaseIntentPage from "@/pages/PurchaseIntentPage";
import RecommendationsPage from "@/pages/RecommendationsPage";
import ReportsPage from "@/pages/ReportsPage";
import SettingsPage from "@/pages/SettingsPage";
import VideoPreviewPage from "@/pages/VideoPreviewPage";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuthStore } from "@/store/authStore";

export default function App() {
  const hydrate = useAuthStore((s) => s.hydrate);

  useEffect(() => {
    hydrate();
    const isDark = localStorage.getItem("rv_theme") !== "light";
    document.documentElement.classList.toggle("dark", isDark);
  }, [hydrate]);

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/upload" element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
      <Route path="/processing" element={<ProtectedRoute><ProcessingPage /></ProtectedRoute>} />
      <Route path="/timeline" element={<ProtectedRoute><TimelinePage /></ProtectedRoute>} />
      <Route path="/analytics" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
      <Route path="/purchase-intent" element={<ProtectedRoute><PurchaseIntentPage /></ProtectedRoute>} />
      <Route path="/recommendations" element={<ProtectedRoute><RecommendationsPage /></ProtectedRoute>} />
      <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      <Route path="/video-preview" element={<ProtectedRoute><VideoPreviewPage /></ProtectedRoute>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
