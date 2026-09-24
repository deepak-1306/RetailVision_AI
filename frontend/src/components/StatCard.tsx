import React from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export function StatCard({
  label, value, icon: Icon, trend, accent = "brand",
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  accent?: "brand" | "emerald" | "amber" | "rose";
}) {
  const accentClasses: Record<string, string> = {
    brand: "bg-brand-500/10 text-brand-500",
    emerald: "bg-emerald-500/10 text-emerald-500",
    amber: "bg-amber-500/10 text-amber-500",
    rose: "bg-rose-500/10 text-rose-500",
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <Card className="p-5 hover:shadow-card-hover transition-shadow">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
            <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">{value}</p>
            {trend && <p className="mt-1 text-xs text-emerald-500">{trend}</p>}
          </div>
          <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", accentClasses[accent])}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
