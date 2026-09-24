import React, { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Card } from "@/components/ui/Card";
import { useAuthStore } from "@/store/authStore";

export default function LoginPage() {
  const [params] = useSearchParams();
  const isRegisterDefault = params.get("mode") === "register";
  const [mode, setMode] = useState<"login" | "register">(isRegisterDefault ? "register" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [storeName, setStoreName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login, register, error, clearError } = useAuthStore();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    clearError();
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register({ email, password, full_name: fullName, store_name: storeName || undefined });
      }
      navigate("/dashboard");
    } catch {
      // error is surfaced via the store
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="w-full max-w-md">
        <div className="mb-8 flex items-center justify-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700">
            <Activity className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold text-white">RetailVision AI</span>
        </div>

        <Card className="bg-slate-900 border-slate-800 p-8">
          <div className="mb-6 flex rounded-xl bg-slate-800 p-1">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); clearError(); }}
                className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
                  mode === m ? "bg-brand-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                {m === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <Label className="text-slate-300">Full name</Label>
                <Input value={fullName} onChange={(e) => setFullName(e.target.value)} required placeholder="Jane Manager" />
              </div>
            )}
            <div>
              <Label className="text-slate-300">Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@store.com" />
            </div>
            {mode === "register" && (
              <div>
                <Label className="text-slate-300">Store name (optional)</Label>
                <Input value={storeName} onChange={(e) => setStoreName(e.target.value)} placeholder="Downtown Flagship" />
              </div>
            )}
            <div>
              <Label className="text-slate-300">Password</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} placeholder="••••••••" />
            </div>

            {error && <p className="text-sm text-rose-400">{error}</p>}

            <Button type="submit" className="w-full" size="lg" disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {mode === "login" ? "Sign In" : "Create Account"}
            </Button>

            {mode === "login" && (
              <button
                type="button"
                onClick={() => { setEmail("deepak@store.com"); setPassword("admin123"); }}
                className="w-full rounded-xl border border-indigo-500/30 bg-indigo-500/10 py-2.5 text-sm font-medium text-indigo-400 hover:bg-indigo-500/20 transition-colors"
              >
                ⚡ Use Demo Account (with real store data)
              </button>
            )}
          </form>
        </Card>

        <p className="mt-6 text-center text-sm text-slate-500">
          <Link to="/" className="hover:text-slate-300">← Back to home</Link>
        </p>
      </motion.div>
    </div>
  );
}
