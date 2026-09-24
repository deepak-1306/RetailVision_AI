import React from "react";
import { Sidebar } from "./Sidebar";
import { Navbar } from "./Navbar";

export function DashboardLayout({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <div className="flex-1 min-w-0">
        <Navbar title={title} />
        <main className="p-4 lg:p-8 max-w-[1600px] mx-auto">{children}</main>
      </div>
    </div>
  );
}
