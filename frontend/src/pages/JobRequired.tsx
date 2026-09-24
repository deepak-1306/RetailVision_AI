import React from "react";
import { useNavigate } from "react-router-dom";
import { FolderSearch } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function JobRequired() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <FolderSearch className="h-10 w-10 text-slate-400 mb-3" />
      <p className="text-slate-500 dark:text-slate-400 mb-4">Select a processed video from your dashboard to view this page.</p>
      <Button onClick={() => navigate("/dashboard")}>Go to Dashboard</Button>
    </div>
  );
}
