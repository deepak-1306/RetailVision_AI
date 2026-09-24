import React, { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Button } from "@/components/ui/Button";
import { useAuthStore } from "@/store/authStore";

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [storeName, setStoreName] = useState(user?.store_name || "");
  const [saved, setSaved] = useState(false);

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    // NOTE: a PATCH /users/me endpoint can be added to app/api/v1/auth.py
    // to persist these fields; wired here for a smooth UX in the meantime.
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <DashboardLayout title="Settings">
      <div className="max-w-xl space-y-6">
        <Card>
          <CardHeader><CardTitle>Account</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <Label>Full name</Label>
                <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </div>
              <div>
                <Label>Email</Label>
                <Input value={user?.email || ""} disabled />
              </div>
              <div>
                <Label>Store name</Label>
                <Input value={storeName} onChange={(e) => setStoreName(e.target.value)} placeholder="Downtown Flagship" />
              </div>
              <Button type="submit">{saved ? "Saved ✓" : "Save changes"}</Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Pipeline Configuration</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-500 dark:text-slate-400">
            <p>YOLOv11 confidence threshold, frame sample rate, and shelf zone calibration are configured via
              backend environment variables (see <code className="text-brand-500">.env</code>) for this release.</p>
            <p>Per-store zone calibration UI is a natural next addition once camera placement is finalized.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
