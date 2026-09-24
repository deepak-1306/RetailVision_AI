import React from "react";
import { cn } from "@/lib/utils";

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800", className)}>
      <div
        className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400 transition-all duration-500"
        style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
      />
    </div>
  );
}
