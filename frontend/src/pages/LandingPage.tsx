import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity, Camera, Brain, TrendingUp, Lightbulb, FileText, ArrowRight, CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const features = [
  { icon: Camera, title: "Computer Vision Pipeline", desc: "YOLOv11 detection + ByteTrack multi-object tracking follows every customer through your store in real time." },
  { icon: Brain, title: "Behaviour Recognition", desc: "Classifies viewing, touching, picking, returning, and more using a Video Swin Transformer-based engine." },
  { icon: TrendingUp, title: "Purchase Intent Scoring", desc: "XGBoost predicts a 0–100 purchase intent score per customer from dwell time, touches, and picks." },
  { icon: Lightbulb, title: "AI Recommendations", desc: "Rule-based retail intelligence turns behaviour patterns into concrete merchandising actions." },
  { icon: FileText, title: "Downloadable Reports", desc: "One-click, boardroom-ready PDF reports combining every stage of the analysis." },
  { icon: Activity, title: "Live Dashboard", desc: "Beautiful charts, heatmaps, and a customer journey view — updated as your video processes." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_-10%,rgba(99,102,241,0.25),transparent_50%)]" />
      <header className="relative z-10 flex items-center justify-between px-6 lg:px-16 h-20">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700">
            <Activity className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold">RetailVision AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/login"><Button variant="ghost">Log in</Button></Link>
          <Link to="/login?mode=register"><Button>Get Started</Button></Link>
        </div>
      </header>

      <section className="relative z-10 px-6 lg:px-16 pt-16 pb-24 text-center max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <span className="inline-block rounded-full border border-brand-500/40 bg-brand-500/10 px-4 py-1 text-sm text-brand-300 mb-6">
            AI-Powered Retail Decision Support
          </span>
          <h1 className="text-4xl lg:text-6xl font-extrabold leading-tight">
            Turn CCTV footage into <span className="text-brand-400">retail intelligence</span>
          </h1>
          <p className="mt-6 text-lg text-slate-400 max-w-2xl mx-auto">
            Upload any in-store camera feed. RetailVision AI detects and tracks every customer, classifies their
            behaviour at the shelf, predicts purchase intent, and tells your team exactly what to fix — today.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4">
            <Link to="/login?mode=register">
              <Button size="lg">
                Start analyzing free <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/login">
              <Button size="lg" variant="outline">Sign in</Button>
            </Link>
          </div>
        </motion.div>
      </section>

      <section className="relative z-10 px-6 lg:px-16 pb-24 max-w-6xl mx-auto">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
            >
              <Card className="bg-slate-900/60 border-slate-800 p-6 h-full">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/10 text-brand-400 mb-4">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="font-semibold mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400">{f.desc}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="relative z-10 px-6 lg:px-16 pb-24 max-w-4xl mx-auto">
        <Card className="bg-gradient-to-br from-brand-600/20 to-slate-900 border-brand-500/30 p-10 text-center">
          <h2 className="text-2xl font-bold mb-3">Built for hackathon speed, ready for production</h2>
          <ul className="mt-6 grid gap-3 sm:grid-cols-2 text-left max-w-md mx-auto">
            {["FastAPI + Celery async pipeline", "React 19 dashboard", "PostgreSQL-ready schema", "Dockerized end-to-end"].map((t) => (
              <li key={t} className="flex items-center gap-2 text-sm text-slate-300">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" /> {t}
              </li>
            ))}
          </ul>
        </Card>
      </section>
    </div>
  );
}
