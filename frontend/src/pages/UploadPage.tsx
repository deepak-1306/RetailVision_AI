import React, { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { UploadCloud, FileVideo, Loader2 } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/Progress";
import { uploadVideo } from "@/lib/api";
import { useJobStore } from "@/store/jobStore";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const setSelectedJobId = useJobStore((s) => s.setSelectedJobId);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
  }, []);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const { job_id } = await uploadVideo(file, setUploadPct);
      setSelectedJobId(job_id);
      navigate("/processing");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <DashboardLayout title="Upload Video">
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>Upload Retail CCTV Footage</CardTitle>
          </CardHeader>
          <CardContent>
            <motion.div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              animate={{ borderColor: dragOver ? "#6366f1" : "#cbd5e1" }}
              className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer"
              onClick={() => document.getElementById("file-input")?.click()}
            >
              <input
                id="file-input"
                type="file"
                accept=".mp4,.avi,.mov,.mkv"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              {file ? (
                <>
                  <FileVideo className="h-10 w-10 text-brand-500 mb-3" />
                  <p className="font-medium text-slate-800 dark:text-slate-100">{file.name}</p>
                  <p className="text-xs text-slate-400 mt-1">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
                </>
              ) : (
                <>
                  <UploadCloud className="h-10 w-10 text-slate-400 mb-3" />
                  <p className="font-medium text-slate-600 dark:text-slate-300">Drag & drop your CCTV video here</p>
                  <p className="text-xs text-slate-400 mt-1">or click to browse — MP4, AVI, MOV, MKV up to 500MB</p>
                </>
              )}
            </motion.div>

            {uploading && (
              <div className="mt-4">
                <Progress value={uploadPct} />
                <p className="mt-1 text-xs text-slate-400">{uploadPct}% uploaded</p>
              </div>
            )}

            {error && <p className="mt-4 text-sm text-rose-500">{error}</p>}

            <Button className="mt-6 w-full" size="lg" disabled={!file || uploading} onClick={handleUpload}>
              {uploading && <Loader2 className="h-4 w-4 animate-spin" />}
              Start AI Analysis
            </Button>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
