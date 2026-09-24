import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBehaviourLabel(behaviour: string): string {
  return behaviour
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds && seconds !== 0) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

export function intentColor(label: string): string {
  switch (label) {
    case "high":
      return "text-emerald-500 bg-emerald-500/10";
    case "medium":
      return "text-amber-500 bg-amber-500/10";
    default:
      return "text-rose-500 bg-rose-500/10";
  }
}

export function priorityColor(priority: string): string {
  switch (priority) {
    case "high":
      return "border-rose-500/40 bg-rose-500/5 text-rose-600 dark:text-rose-400";
    case "medium":
      return "border-amber-500/40 bg-amber-500/5 text-amber-600 dark:text-amber-400";
    default:
      return "border-emerald-500/40 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400";
  }
}
