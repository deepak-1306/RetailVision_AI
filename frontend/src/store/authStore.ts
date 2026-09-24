import { create } from "zustand";
import type { User } from "@/types";
import { fetchMe, loginUser, registerUser } from "@/lib/api";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: { email: string; full_name: string; password: string; store_name?: string }) => Promise<void>;
  logout: () => void;
  hydrate: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: JSON.parse(localStorage.getItem("rv_user") || "null"),
  isAuthenticated: !!localStorage.getItem("rv_access_token"),
  isLoading: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const tokens = await loginUser(email, password);
      localStorage.setItem("rv_access_token", tokens.access_token);
      localStorage.setItem("rv_refresh_token", tokens.refresh_token);
      localStorage.setItem("rv_user", JSON.stringify(tokens.user));
      set({ user: tokens.user, isAuthenticated: true, isLoading: false });
    } catch (err: any) {
      set({ error: err?.response?.data?.detail || "Login failed", isLoading: false });
      throw err;
    }
  },

  register: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const tokens = await registerUser(payload);
      localStorage.setItem("rv_access_token", tokens.access_token);
      localStorage.setItem("rv_refresh_token", tokens.refresh_token);
      localStorage.setItem("rv_user", JSON.stringify(tokens.user));
      set({ user: tokens.user, isAuthenticated: true, isLoading: false });
    } catch (err: any) {
      set({ error: err?.response?.data?.detail || "Registration failed", isLoading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("rv_access_token");
    localStorage.removeItem("rv_refresh_token");
    localStorage.removeItem("rv_user");
    set({ user: null, isAuthenticated: false });
  },

  hydrate: async () => {
    const token = localStorage.getItem("rv_access_token");
    if (!token) return;
    try {
      const user = await fetchMe();
      localStorage.setItem("rv_user", JSON.stringify(user));
      set({ user, isAuthenticated: true });
    } catch {
      localStorage.removeItem("rv_access_token");
      set({ user: null, isAuthenticated: false });
    }
  },

  clearError: () => set({ error: null }),
}));

export function useThemeStore() {
  const stored = localStorage.getItem("rv_theme");
  return stored === "light" ? "light" : "dark";
}
