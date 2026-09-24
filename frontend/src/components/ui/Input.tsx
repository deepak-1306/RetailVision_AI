import React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm outline-none",
        "focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition-shadow",
        "placeholder:text-slate-400",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
