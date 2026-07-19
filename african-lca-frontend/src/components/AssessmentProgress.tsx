'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Loader2, Sprout, Factory } from 'lucide-react';
import type { AssessmentProgressEvent } from '@/lib/api';

// A staged loading view for the (1-3 minute) LCA solve. The stages mirror the REAL pipeline
// the engine runs — inventory build, dataset matching, supply-chain solve, characterization,
// report. When a `live` event stream is provided (from the /assess/stream SSE endpoint) it
// tracks the ACTUAL engine stage in real time; without one it falls back to a calibrated
// timer. Either way it holds on the last stage until the result lands (the parent unmounts
// this on completion), so it never claims "done" early or sticks at 100%.

type Variant = 'farm' | 'processing';
interface Stage { label: string; detail: string; est: number } // est = seconds (timer fallback only)

// Backend stage keys, in order, aligned 1:1 with the display stages below.
const STAGE_ORDER = ['prepare', 'inventory', 'match', 'solve', 'characterize', 'report'];

const FARM_STAGES: Stage[] = [
  { label: 'Reading your farm data', detail: 'Validating inputs and preparing the product system.', est: 8 },
  { label: 'Building the life-cycle inventory', detail: 'Field emissions from IPCC 2019 (N₂O, CH₄) for each crop.', est: 20 },
  { label: 'Matching inputs to datasets', detail: 'Linking fertiliser, fuel and inputs to ecoinvent and Agribalyse.', est: 25 },
  { label: 'Solving the supply chain', detail: 'Cradle-to-gate matrix solve across every linked process.', est: 55 },
  { label: 'Characterizing impacts', detail: 'Applying ReCiPe 2016 / EF 3.1 factors across the categories.', est: 30 },
  { label: 'Scoring and compiling your report', detail: 'Single score, pedigree data quality and the ISO report.', est: 14 },
];

const PROCESSING_STAGES: Stage[] = [
  { label: 'Reading your facility data', detail: 'Validating inputs and preparing the product system.', est: 8 },
  { label: 'Building the life-cycle inventory', detail: 'Purchased energy, materials, packaging, waste and transport.', est: 15 },
  { label: 'Matching inputs to datasets', detail: 'Linking utilities and materials to ecoinvent and Agribalyse.', est: 25 },
  { label: 'Solving the supply chain', detail: 'Cradle-to-gate matrix solve across every linked process.', est: 55 },
  { label: 'Characterizing and allocating', detail: 'ReCiPe 2016 / EF 3.1 factors, then co-product allocation.', est: 30 },
  { label: 'Compiling your report', detail: 'Single score, pedigree data quality and the ISO report.', est: 14 },
];

function fmt(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export default function AssessmentProgress({
  variant = 'farm',
  live,
}: {
  variant?: Variant;
  live?: AssessmentProgressEvent | null;
}) {
  const stages = variant === 'processing' ? PROCESSING_STAGES : FARM_STAGES;
  const total = useMemo(() => stages.reduce((sum, s) => sum + s.est, 0), [stages]);
  const cumulative = useMemo(() => {
    let acc = 0;
    return stages.map((s) => (acc += s.est));
  }, [stages]);

  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed((e) => e + 0.25), 250);
    return () => clearInterval(id);
  }, []);

  // Live mode: track the real engine stage, monotonically (never regress — e.g. multi-crop
  // farms re-enter earlier stages per crop, which should not rewind the bar).
  const [liveIndex, setLiveIndex] = useState<number | null>(null);
  const stageEnteredAt = useRef(0);
  useEffect(() => {
    if (!live) return;
    const idx = STAGE_ORDER.indexOf(live.stage);
    if (idx < 0) return;
    setLiveIndex((prev) => (prev == null ? idx : Math.max(prev, idx)));
  }, [live]);
  useEffect(() => {
    stageEnteredAt.current = elapsed; // reset the within-stage creep when the stage advances
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveIndex]);

  const liveMode = liveIndex != null;
  let currentIndex: number;
  let pct: number;
  let overrun = false;

  if (liveMode) {
    currentIndex = Math.min(liveIndex as number, stages.length - 1);
    let frac: number;
    if (live?.stage === 'solve' && live.total) {
      frac = Math.min(1, (live.index || 0) / live.total); // real sub-progress across inputs
    } else {
      // gentle creep so a long stage (e.g. cold-engine index build) doesn't look frozen
      frac = Math.min(0.85, Math.max(0, elapsed - stageEnteredAt.current) / 12);
    }
    pct = Math.min(97, ((currentIndex + frac) / stages.length) * 100);
  } else {
    currentIndex = cumulative.findIndex((end) => elapsed < end);
    if (currentIndex === -1) currentIndex = stages.length - 1; // past the estimate: hold on last
    overrun = elapsed > total;
    pct = Math.min(95, (elapsed / total) * 100); // cap < 100 until the result actually lands
  }

  // During solve, the engine sends the input/process name in `detail` plus index/total.
  // Prefer that name over a generic "Process N of M" (farm crops and facility inputs alike).
  const liveDetail = (() => {
    if (!liveMode || !live) return undefined;
    if (live.stage === 'solve' && live.total) {
      const name = (live.detail || '').trim();
      const counter = `${live.index} of ${live.total}`;
      if (name) {
        // Farm path sometimes already embeds "(1/2)" in detail — avoid duplicating.
        if (/\(\d+\s*\/\s*\d+\)/.test(name) || /\d+\s+of\s+\d+/i.test(name)) {
          return name;
        }
        return `${name} · ${counter}`;
      }
      return `Process ${counter}`;
    }
    return live.detail || undefined;
  })();

  const HeadIcon = variant === 'processing' ? Factory : Sprout;

  return (
    <div className="mx-auto max-w-xl py-4">
      <div className="text-center">
        <div className="relative inline-grid place-items-center w-16 h-16">
          <motion.span
            className="absolute inset-0 rounded-2xl bg-moss/15"
            animate={{ scale: [1, 1.12, 1], opacity: [0.6, 0.3, 0.6] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          />
          <div className="relative grid place-items-center w-16 h-16 rounded-2xl bg-spruce text-white">
            <HeadIcon className="w-8 h-8" />
          </div>
        </div>
        <h3 className="mt-4 text-xl font-semibold text-ink">Running your assessment</h3>
        <p className="mt-1 text-sm text-muted">
          Building a real ISO 14040/14044 inventory — this usually takes 2 to 3 minutes.
        </p>
      </div>

      {/* Progress bar */}
      <div className="mt-6">
        <div className="relative w-full h-2 rounded-full bg-line/60 overflow-hidden">
          <motion.div
            className="absolute inset-y-0 left-0 rounded-full bg-moss"
            animate={{ width: `${pct}%` }}
            transition={{ ease: 'linear', duration: 0.25 }}
          />
        </div>
        <div className="mt-1.5 flex justify-between text-xs text-muted">
          <span aria-live="polite">
            Step {currentIndex + 1} of {stages.length}: {stages[currentIndex].label}
          </span>
          <span>{fmt(elapsed)}</span>
        </div>
      </div>

      {/* Stage list */}
      <ol className="mt-6 space-y-3">
        {stages.map((stage, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          return (
            <li key={stage.label} className="flex items-start gap-3">
              <span className="mt-0.5 shrink-0">
                {done ? (
                  <CheckCircle2 className="w-5 h-5 text-moss" />
                ) : active ? (
                  <Loader2 className="w-5 h-5 text-spruce animate-spin" />
                ) : (
                  <span className="grid place-items-center w-5 h-5">
                    <span className="w-2 h-2 rounded-full bg-line" />
                  </span>
                )}
              </span>
              <div className={active ? '' : done ? 'opacity-90' : 'opacity-45'}>
                <div className="text-sm font-medium text-ink">{stage.label}</div>
                {active && (
                  <div className="text-xs text-muted mt-0.5">
                    {overrun ? 'Almost there — finalizing the last calculations…' : (active && liveDetail) || stage.detail}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <p className="mt-6 text-center text-xs text-muted">
        Please keep this tab open. Your results will appear automatically when the solve completes.
      </p>
    </div>
  );
}
