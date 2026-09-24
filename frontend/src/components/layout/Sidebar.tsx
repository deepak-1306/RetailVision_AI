import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, UploadCloud, Clock, BarChart3, TrendingUp,
  Lightbulb, FileText, Settings as SettingsIcon, Activity, Radio, Film,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/upload", label: "Upload Video", icon: UploadCloud },
  { to: "/video-preview", label: "Video Preview", icon: Film },
  { to: "/timeline", label: "Behaviour Timeline", icon: Clock },
  { to: "/analytics", label: "Customer Analytics", icon: BarChart3 },
  { to: "/purchase-intent", label: "Purchase Intent", icon: TrendingUp },
  { to: "/recommendations", label: "AI Recommendations", icon: Lightbulb },
  { to: "/reports", label: "Reports & Insights", icon: FileText },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export function Sidebar() {
  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 h-screen sticky top-0">
      <div className="flex items-center gap-2 px-6 h-16 border-b border-slate-200 dark:border-slate-800">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700">
          <Activity className="h-4 w-4 text-white" />
        </div>
        <span className="font-bold text-slate-900 dark:text-white">RetailVision AI</span>
      </div>
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 text-xs text-slate-400 border-t border-slate-200 dark:border-slate-800">
        RetailVision AI v1.0 · Hackathon Build
      </div>
    </aside>
  );
}
