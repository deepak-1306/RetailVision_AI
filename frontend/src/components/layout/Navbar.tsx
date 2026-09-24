import React, { useEffect, useState } from "react";
import { Moon, Sun, LogOut, User as UserIcon } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/Button";
import { useNavigate } from "react-router-dom";

export function Navbar({ title }: { title: string }) {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [dark, setDark] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("rv_theme");
    const isDark = stored !== "light";
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("rv_theme", next ? "dark" : "light");
  }

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur px-4 lg:px-8">
      <h1 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h1>
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={toggleTheme} aria-label="Toggle theme">
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <div className="hidden sm:flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-800 px-3 py-1.5">
          <UserIcon className="h-4 w-4 text-slate-500" />
          <span className="text-sm text-slate-700 dark:text-slate-300">{user?.full_name || "Manager"}</span>
        </div>
        <Button variant="outline" size="sm" onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Logout</span>
        </Button>
      </div>
    </header>
  );
}
