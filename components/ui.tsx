import clsx from "clsx";
import type { ReactNode } from "react";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={clsx("rounded-lg border border-white/10 bg-white/[0.045] p-4 shadow-glow backdrop-blur", className)}>{children}</section>;
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{children}</label>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

export const inputClass =
  "w-full rounded-md border border-white/10 bg-command-950/80 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-signal-cyan/70 focus:ring-2 focus:ring-signal-cyan/10";

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "green" | "gold" | "red" | "cyan" }) {
  const tones = {
    neutral: "border-white/10 bg-white/5 text-slate-300",
    green: "border-signal-green/25 bg-signal-green/10 text-signal-green",
    gold: "border-signal-gold/25 bg-signal-gold/10 text-signal-gold",
    red: "border-signal-red/25 bg-signal-red/10 text-signal-red",
    cyan: "border-signal-cyan/25 bg-signal-cyan/10 text-signal-cyan"
  };

  return <span className={clsx("inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function ScoreBar({ value }: { value: number }) {
  return (
    <div className="h-2 w-full rounded-full bg-command-950">
      <div className="score-track h-2 rounded-full" style={{ width: `${Math.max(1, Math.min(10, value)) * 10}%` }} />
    </div>
  );
}
