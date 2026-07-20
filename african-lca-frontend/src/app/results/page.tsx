'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import RequireAuth from '@/components/RequireAuth';
import ConfirmDialog from '@/components/ConfirmDialog';

// Force dynamic rendering to prevent static generation issues
export const dynamic = 'force-dynamic';
import { 
  BarChart3, 
  Droplets, 
  Leaf, 
  Sun, 
  TreePine,
  Award,
  AlertTriangle,
  CheckCircle,
  Download,
  Share,
  ArrowRight,
  Pencil,
  Trash2
} from 'lucide-react';
import {
  ResponsiveContainer,
  RadialBarChart,
  RadialBar
} from 'recharts';
import Layout from '@/components/Layout';
import ResultsChat from '@/components/ResultsChat';
import ISOReport from '@/components/ISOReport';
import RecommendationsPanel from '@/components/RecommendationsPanel';
import { assessmentAPI, getScoreInterpretation, ApiError } from '@/lib/api';
import { AssessmentResult, SingleScoreResult } from '@/types/assessment';

// Color schemes for charts
// const IMPACT_COLORS = [
//   '#10B981', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444',
//   '#06B6D4', '#84CC16', '#F97316', '#EC4899', '#6366F1'
// ];

const SCORE_COLORS = {
  excellent: '#10B981',
  good: '#3B82F6', 
  typical: '#F59E0B',
  'above-average': '#F97316',
  'high-impact': '#EF4444',
};

type ScenarioDeltaEntry = {
  title: string;
  scenario_id: string;
  delta_midpoints: Record<string, { value: number; baseline?: number; scenario?: number }>;
  delta_single_score: number | null;
};

/** Tornado view of one scenario: per-category % change vs baseline as diverging bars,
 * plus a signed/colored single-score badge. Green = lower impact, red = higher. */
function ScenarioTornado({
  delta,
  baselineSingleScore,
}: {
  delta: ScenarioDeltaEntry;
  baselineSingleScore?: number;
}) {
  const rows = Object.entries(delta.delta_midpoints)
    .map(([cat, d]) => ({
      cat,
      pct: d.baseline ? (d.value / d.baseline) * 100 : null,
    }))
    .filter((r): r is { cat: string; pct: number } => r.pct !== null && Number.isFinite(r.pct))
    .sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct));
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.pct)));
  const ss = delta.delta_single_score;
  const ssPct = ss != null && baselineSingleScore ? (ss / baselineSingleScore) * 100 : null;

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <p className="font-semibold text-gray-900 text-sm">{delta.title}</p>
        {ss != null && (
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
              ss < 0 ? 'bg-green-50 text-green-700' : ss > 0 ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-gray-600'
            }`}
            title="Change in normalized single score vs baseline"
          >
            single score {ss < 0 ? '▼' : ss > 0 ? '▲' : ''}
            {ssPct != null ? ` ${ssPct > 0 ? '+' : ''}${ssPct.toFixed(1)}%` : ` ${ss.toPrecision(3)}`}
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        {rows.map((r) => {
          const half = (Math.abs(r.pct) / maxAbs) * 50; // percent of row width per side
          const positive = r.pct > 0;
          return (
            <div key={r.cat} className="flex items-center gap-2 text-xs">
              <span className="w-40 shrink-0 truncate text-gray-700" title={r.cat}>
                {r.cat}
              </span>
              <div className="relative flex-1 h-4 rounded bg-gray-50">
                <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-300" />
                <div
                  className={`absolute top-0 bottom-0 rounded-sm ${positive ? 'bg-red-400' : 'bg-green-500'}`}
                  style={positive ? { left: '50%', width: `${half}%` } : { right: '50%', width: `${half}%` }}
                />
              </div>
              <span className={`w-14 shrink-0 text-right font-mono ${positive ? 'text-red-600' : 'text-green-700'}`}>
                {r.pct > 0 ? '+' : ''}
                {r.pct.toFixed(0)}%
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[11px] text-gray-400">
        Green = lower impact than baseline, red = higher; bars scaled to the largest change. Saved as{' '}
        {delta.scenario_id.slice(0, 8)}…
      </p>
    </div>
  );
}

interface ResultsContentProps {
  assessmentId: string | null;
  isProcessing?: boolean;
}

function ResultsContent({ assessmentId, isProcessing = false }: ResultsContentProps) {
  const router = useRouter();
  const [results, setResults] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [shareLabel, setShareLabel] = useState('Share Results');
  const [pendingDelete, setPendingDelete] = useState(false);
  const [pendingRerun, setPendingRerun] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [canRerun, setCanRerun] = useState(false);
  /** Dual FU: engine always stores per-kg midpoints; per-ha comes from functional_units. */
  const [fuMode, setFuMode] = useState<'per_kg' | 'per_ha'>('per_kg');
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [scenarioDeltas, setScenarioDeltas] = useState<Array<{
    title: string;
    scenario_id: string;
    delta_midpoints: Record<string, { value: number; baseline?: number; scenario?: number }>;
    delta_single_score: number | null;
  }>>([]);
  const [methodBusy, setMethodBusy] = useState(false);
  const [mcBusy, setMcBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState<string | null>(null);
  /** Inline, screen-reader-friendly status for the researcher panel (replaces alert()). */
  const [panelError, setPanelError] = useState<string | null>(null);

  const handleDownload = () => window.print();

  const runScenario = async (patch: {
    name: string;
    yield_scale?: number;
    n_rate_scale?: number;
    diesel_scale?: number;
  }) => {
    if (!assessmentId) return;
    setScenarioBusy(true);
    setPanelError(null);
    try {
      const res = await assessmentAPI.createScenario(assessmentId, patch);
      const entry = {
        title: res.title,
        scenario_id: res.scenario_id,
        delta_midpoints: res.delta_midpoints,
        delta_single_score: res.delta_single_score,
      };
      // Accumulate scenarios (replace one with the same title, else append) so a researcher
      // can compare several counterfactuals side by side rather than overwriting.
      setScenarioDeltas((prev) => {
        const rest = prev.filter((s) => s.title !== entry.title);
        return [...rest, entry];
      });
    } catch (e) {
      console.error(e);
      setPanelError(e instanceof Error ? e.message : 'Scenario compare failed');
    } finally {
      setScenarioBusy(false);
    }
  };

  const persistResults = (res: AssessmentResult) => {
    setResults(res);
    try {
      localStorage.setItem(`assessment_${assessmentId}`, JSON.stringify(res));
    } catch {
      /* ignore */
    }
  };

  // Non-destructive by default: recharacterizing populates method_variants for the
  // side-by-side table WITHOUT overwriting the primary result. Promoting a variant to
  // primary is an explicit, separate action (applyAsPrimary = true).
  const runRecharacterize = async (method: string, applyAsPrimary = false) => {
    if (!assessmentId) return;
    setMethodBusy(true);
    setPanelError(null);
    try {
      const res = await assessmentAPI.recharacterizeAssessment(assessmentId, method, applyAsPrimary);
      persistResults(res);
    } catch (e) {
      console.error(e);
      setPanelError(e instanceof Error ? e.message : 'Recharacterize failed');
    } finally {
      setMethodBusy(false);
    }
  };

  // Wire the previously-orphaned uncertainty endpoint: re-solve with pedigree MC and
  // refresh the ranges in place, so a saved result without an MC block can gain one.
  const runUncertainty = async () => {
    if (!assessmentId) return;
    setMcBusy(true);
    setPanelError(null);
    try {
      const res = await assessmentAPI.runAssessmentUncertainty(assessmentId);
      persistResults(res);
    } catch (e) {
      console.error(e);
      setPanelError(e instanceof Error ? e.message : 'Monte Carlo run failed');
    } finally {
      setMcBusy(false);
    }
  };

  const runExport = async (
    format: 'json' | 'csv',
    section?: 'impacts' | 'matches' | 'contributions'
  ) => {
    if (!assessmentId) return;
    const key = format === 'csv' && section ? `csv:${section}` : format;
    setExportBusy(key);
    setPanelError(null);
    try {
      await assessmentAPI.downloadAssessmentExport(assessmentId, format, section);
    } catch (e) {
      console.error(e);
      setPanelError(e instanceof Error ? e.message : `Export (${format.toUpperCase()}) failed`);
    } finally {
      setExportBusy(null);
    }
  };

  const activeMidpoints = (() => {
    if (!results) return {} as AssessmentResult['midpoint_impacts'];
    if (fuMode === 'per_ha') {
      const ha = results.functional_units?.per_ha?.midpoint_impacts;
      if (ha && Object.keys(ha).length) return ha as AssessmentResult['midpoint_impacts'];
    }
    return results.midpoint_impacts;
  })();
  const fuUnitLabel = fuMode === 'per_ha' ? 'per ha' : 'per kg';

  const displayName =
    results?.farm_profile?.farm_name
    || results?.facility_profile?.facility_name
    || results?.company_name
    || 'this assessment';

  const handleShare = async () => {
    if (!assessmentId) return;
    try {
      const { share_path } = await assessmentAPI.createShareLink(assessmentId);
      const url = `${window.location.origin}${share_path}`;
      await navigator.clipboard.writeText(url);
      setShareLabel('Share link copied');
    } catch {
      try {
        await navigator.clipboard.writeText(window.location.href);
        setShareLabel('Link copied');
      } catch {
        setShareLabel('Copy failed');
      }
    }
    setTimeout(() => setShareLabel('Share Results'), 2000);
  };

  useEffect(() => {
    if (assessmentId) {
      loadResults(assessmentId);
    } else {
      // Load most recent results or show empty state
      setLoading(false);
    }
  }, [assessmentId, isProcessing]);

  const fetchAssessment = (id: string) =>
    isProcessing ? assessmentAPI.getProcessingAssessment(id) : assessmentAPI.getAssessment(id);

  // A 404 means the assessment no longer exists on the server (deleted, or a stale
  // link). That is different from a transient failure (network / 5xx), where the cached
  // copy is still worth showing.
  const isDeleted = (err: unknown) => err instanceof ApiError && err.status === 404;

  const clearCached = (id: string) => {
    try { localStorage.removeItem(`assessment_${id}`); } catch { /* ignore */ }
  };

  const loadResults = async (id: string) => {
    setLoading(true);
    setError(null);
    setNotFound(false);

    // Cache-first: show the cached copy immediately, then reconcile with the backend.
    const cachedResult = localStorage.getItem(`assessment_${id}`);
    if (cachedResult) {
      try {
        setResults(JSON.parse(cachedResult));
      } catch {
        clearCached(id); // corrupt cache entry
      }
      setLoading(false);
      try {
        const backendResult = await fetchAssessment(id);
        localStorage.setItem(`assessment_${id}`, JSON.stringify(backendResult));
        setResults(backendResult);
      } catch (err) {
        if (isDeleted(err)) {
          // Deleted on the server: stop showing a ghost. Drop the stale cache and
          // switch to a clean not-found state.
          clearCached(id);
          setResults(null);
          setNotFound(true);
        }
        // Otherwise transient: keep the cached view as-is.
      }
      return;
    }

    // No cache: the backend is the only source.
    try {
      const result = await fetchAssessment(id);
      localStorage.setItem(`assessment_${id}`, JSON.stringify(result));
      setResults(result);
    } catch (err) {
      if (isDeleted(err)) {
        setNotFound(true);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load results');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!assessmentId) {
      setCanRerun(false);
      return;
    }
    let active = true;
    assessmentAPI
      .getAssessmentRequest(assessmentId)
      .then(() => {
        if (active) setCanRerun(true);
      })
      .catch(() => {
        if (active) setCanRerun(false);
      });
    return () => {
      active = false;
    };
  }, [assessmentId]);

  const confirmDelete = async () => {
    if (!assessmentId) return;
    setActionBusy(true);
    try {
      await assessmentAPI.deleteAssessment(assessmentId);
      try {
        localStorage.removeItem(`assessment_${assessmentId}`);
      } catch {
        /* ignore */
      }
      router.push('/dashboard/assessments');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete assessment');
      setPendingDelete(false);
    } finally {
      setActionBusy(false);
    }
  };

  const confirmRerun = () => {
    if (!assessmentId) return;
    setPendingRerun(false);
    if (isProcessing) {
      router.push(`/processing-assessment?rerunFrom=${assessmentId}`);
    } else {
      router.push(`/assessment?rerunFrom=${assessmentId}`);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[70vh]">
          <div className="text-center">
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5 }}
              className="mb-8"
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                className="w-20 h-20 border-4 border-green-500 border-t-transparent rounded-full mx-auto mb-6"
              />
              <div className="space-y-2">
                <p className="text-2xl font-bold text-gray-900">Loading your results...</p>
                <p className="text-gray-600">Processing your assessment with our Rust-powered engine</p>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5 }}
                  className="flex items-center justify-center space-x-2 text-sm text-green-600 mt-4"
                >
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <span>Typical processing time: 100-200ms</span>
                </motion.div>
              </div>
            </motion.div>
          </div>
        </div>
      </Layout>
    );
  }

  if (notFound) {
    return (
      <Layout>
        <div className="py-12 px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-2xl mx-auto"
          >
            <div className="bg-white border border-gray-200 rounded-3xl p-12 text-center shadow-xl">
              <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <AlertTriangle className="w-10 h-10 text-gray-400" />
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-3">Assessment not found</h1>
              <p className="text-lg text-gray-600 mb-8">
                This assessment may have been deleted, or the link is out of date.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <button
                  type="button"
                  onClick={() => router.push('/dashboard/assessments')}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-spruce px-6 py-3 font-semibold text-white hover:bg-ink transition-colors"
                >
                  Back to my assessments
                </button>
                <button
                  type="button"
                  onClick={() => router.push('/dashboard')}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-300 px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Go to dashboard
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <div className="py-12 px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-2xl mx-auto"
          >
            <div className="bg-gradient-to-br from-red-50 to-orange-50 border-2 border-red-200 rounded-3xl p-12 text-center shadow-xl">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 15 }}
                className="w-24 h-24 bg-red-500 rounded-full flex items-center justify-center mx-auto mb-6"
              >
                <AlertTriangle className="w-12 h-12 text-white" />
              </motion.div>
              <h1 className="text-3xl font-bold text-gray-900 mb-4">Unable to Load Results</h1>
              <p className="text-lg text-gray-700 mb-8">{error}</p>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => window.location.href = '/assessment'}
                className="bg-gradient-to-r from-green-600 to-emerald-600 text-white px-8 py-4 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-all shadow-lg inline-flex items-center space-x-2"
              >
                <span>Start New Assessment</span>
                <ArrowRight className="w-5 h-5" />
              </motion.button>
            </div>
          </motion.div>
        </div>
      </Layout>
    );
  }

  if (!results) {
    return (
      <Layout>
        <div className="py-12 px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-4xl mx-auto"
          >
            <div className="bg-gradient-to-br from-gray-50 to-green-50/50 border-2 border-gray-200 rounded-3xl p-16 text-center shadow-xl">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 15 }}
                className="w-24 h-24 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-8 shadow-xl"
              >
                <BarChart3 className="w-12 h-12 text-white" />
              </motion.div>
              <h1 className="text-4xl font-bold text-gray-900 mb-4">
                No Assessment Results Yet
              </h1>
              <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto leading-relaxed">
                Complete a farm assessment to see your sustainability analysis and recommendations.
              </p>
              <motion.a
                href="/assessment"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="bg-gradient-to-r from-green-600 to-emerald-600 text-white px-10 py-5 rounded-2xl font-bold text-lg hover:from-green-700 hover:to-emerald-700 inline-flex items-center space-x-3 shadow-xl"
              >
                <BarChart3 className="w-6 h-6" />
                <span>Start Assessment</span>
                <ArrowRight className="w-5 h-5" />
              </motion.a>
            </div>
          </motion.div>
        </div>
      </Layout>
    );
  }

  // Helper function to extract numeric value from result data
  const extractValue = (data: unknown): number => {
    if (typeof data === 'number') {
      return data;
    }
    if (typeof data === 'object' && data !== null) {
      if ('value' in data && typeof data.value === 'number') {
        return data.value;
      }
    }
    return 0;
  };

  // Helper to check if value is already per-kg
  const isAlreadyPerKg = (data: unknown): boolean => {
    if (typeof data === 'object' && data !== null) {
      if ('unit' in data && typeof data.unit === 'string') {
        return data.unit.includes('per kg');
      }
    }
    return false;
  };


  // Helper function to format display values
  const formatDisplayValue = (value: number | undefined, precision: number = 1, categoryName?: string): string => {
    // Handle undefined or null values
    if (value === undefined || value === null || isNaN(value)) {
      return 'N/A';
    }

    // Special handling for zero values in water-related categories
    if (value === 0) {
      if (categoryName === 'Water consumption' || categoryName === 'Water Use') {
        return '0 (Rainfed)';
      }
      if (categoryName === 'Water scarcity') {
        return '0 (No irrigation)';
      }
      // For other categories, show N/A if truly zero
      return 'N/A';
    }
    if (value < 0.01) return value.toExponential(2);
    if (value < 1) return value.toFixed(precision + 1);
    if (value < 1000) return value.toFixed(precision);
    return value.toLocaleString(undefined, { maximumFractionDigits: precision });
  };

  // Helper function to calculate per-unit impacts
  const calculatePerUnitImpact = (totalImpact: number, totalQuantityKg: number): number => {
    if (totalQuantityKg === 0) return 0;
    return totalImpact / totalQuantityKg;
  };

  // Farm results key the breakdown by crop, processing results by product. Either may be
  // absent, so callers below must never assume the field exists.
  const breakdown = results.breakdown_by_food ?? results.breakdown_by_product ?? {};

  // Calculate total production quantity from breakdown
  const getTotalProductionQuantity = (): number => {
    // Try to extract from crop breakdown data or use a reasonable estimate
    const cropEntries = Object.entries(breakdown);
    if (cropEntries.length > 0) {
      // Extract quantity from crop name if it includes quantity info
      // Look for patterns like "Cassava (48000kg)" in crop names
      let totalQuantity = 0;
      cropEntries.forEach(([cropName]) => {
        const quantityMatch = cropName.match(/\((\d+(?:,\d+)*)kg\)/);
        if (quantityMatch) {
          const quantity = parseInt(quantityMatch[1].replace(/,/g, ''));
          totalQuantity += quantity;
        }
      });
      
      if (totalQuantity > 0) return totalQuantity;
    }
    
    // Fallback: assume 1 kg if we can't determine the quantity
    // This will show total impacts but with per-kg units
    return 1;
  };

  const totalProductionKg = getTotalProductionQuantity();

  // Single score: a normalized ReCiPe score in µPt per kg (person-equivalents ×1e6),
  // with a qualitative band from the backend. Falls back to the legacy 0-1 interpretation.
  const singleScoreValue = extractValue(results.single_score);
  const scoreBand = (results.single_score as { band?: string })?.band;
  const BAND_MAP: Record<string, { category: string; title: string; description: string; color: string; recommendations: string[] }> = {
    Low: { category: 'excellent', title: 'Low Impact', color: 'text-green-700 bg-green-50 border-green-200',
           description: 'Low normalized environmental footprint per kg (ReCiPe 2016 single score).',
           recommendations: ['Maintain current practices', 'Document methods for certification', 'Share as a regional benchmark'] },
    Moderate: { category: 'typical', title: 'Moderate Impact', color: 'text-yellow-700 bg-yellow-50 border-yellow-200',
                description: 'Typical normalized environmental footprint per kg for agri-food.',
                recommendations: ['Optimize fertiliser rates to cut field N2O', 'Improve fuel/energy efficiency', 'Target the largest-contributing category below'] },
    High: { category: 'high-impact', title: 'Higher Impact', color: 'text-red-700 bg-red-50 border-red-200',
            description: 'Higher normalized footprint per kg — see the recommendations to reduce it.',
            recommendations: ['Reduce synthetic N inputs / split applications', 'Switch to lower-carbon energy sources', 'Review the dominant impact category below'] },
  };
  const scoreInterpretation = (scoreBand && BAND_MAP[scoreBand]) || getScoreInterpretation(singleScoreValue);
  const scoreUnit = (results.single_score as { unit?: string })?.unit || '';
  const isMicroPoints = scoreUnit.includes('µPt') || scoreUnit.includes('Pt');

  // Drive the gauge off the SAME calibrated band cutoffs the ISO BandStrip uses, so the
  // headline gauge and the report agree on where "High" begins. The High cutoff is the
  // benchmark's ~67th percentile, so we place it at ~67% of the arc (fullScale = high/0.67).
  // Fall back to the legacy 2000 µPt full-scale only when cutoffs are unavailable.
  const bandCutoffs = (results.single_score as SingleScoreResult)?.band_cutoffs;
  const gaugeFullScale =
    isMicroPoints && bandCutoffs?.high && bandCutoffs.high > 0
      ? bandCutoffs.high / 0.67
      : 2000;
  const scoreData = [{
    name: 'Your Score',
    score: isMicroPoints
      ? Math.min((singleScoreValue / gaugeFullScale) * 100, 100)
      : singleScoreValue * 100,
    fill: SCORE_COLORS[scoreInterpretation.category as keyof typeof SCORE_COLORS]
  }];

  return (
    <Layout>
      <div className="py-12 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-green-50/30 via-white to-emerald-50/30">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center mb-10"
          >
            <motion.div 
              className="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-xl"
              whileHover={{ scale: 1.05, rotate: 5 }}
              transition={{ duration: 0.3 }}
            >
              <Award className="w-10 h-10 text-white" />
            </motion.div>
            <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-8 leading-tight">
              Sustainability Assessment Results
            </h1>
            
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="bg-white/80 backdrop-blur-sm rounded-2xl p-8 shadow-xl border border-white max-w-3xl mx-auto"
            >
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                {results.farm_profile?.farm_name
                  || results.facility_profile?.facility_name
                  || results.company_name
                  || 'Assessment'}
              </h2>
              {results.farm_profile?.farmer_name && (
                <p className="text-gray-600 mb-4">
                  {results.farm_profile.farmer_name}
                </p>
              )}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-6 text-gray-700">
                <div className="flex items-center space-x-2">
                  <span className="text-2xl">📍</span>
                  <span className="font-semibold">
                    {results.country === 'Global' ? 'Canada' : results.country}
                  </span>
                </div>
                <div className="hidden sm:block w-1 h-1 bg-gray-400 rounded-full"></div>
                <div className="flex items-center space-x-2">
                  <span className="text-2xl">📅</span>
                  <span className="font-semibold">{new Date(results.assessment_date).toLocaleDateString('en-US', { 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                  })}</span>
                </div>
              </div>
              
              
            </motion.div>
          </motion.div>

          {/* Score Overview */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mb-12"
          >
            <div className={`rounded-3xl p-10 border-2 shadow-2xl ${scoreInterpretation.color}`}>
              <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
                <div className="text-center lg:text-left flex-1">
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.4 }}
                  >
                    <h3 className="text-3xl font-bold mb-4">
                      Environmental Impact Score
                    </h3>
                    <div className="mb-6">
                      <span className="text-7xl font-black tracking-tight">
                        {isMicroPoints ? singleScoreValue.toFixed(0) : (singleScoreValue * 100).toFixed(1)}
                      </span>
                      <span className="text-2xl font-bold ml-2 opacity-80">
                        {isMicroPoints ? 'µPt/kg' : '%'}
                      </span>
                    </div>
                    <div className="inline-flex items-center space-x-3 mb-4">
                      <div className="text-2xl font-bold">
                        {scoreInterpretation.title}
                      </div>
                      {scoreInterpretation.category === 'excellent' && <span className="text-3xl">🏆</span>}
                      {scoreInterpretation.category === 'good' && <span className="text-3xl">⭐</span>}
                    </div>
                    <p className="text-xl opacity-90 max-w-md leading-relaxed">
                      {scoreInterpretation.description}
                    </p>
                    {(results.single_score as { band_basis?: string })?.band_basis && (
                      <p className="text-xs opacity-70 max-w-md mt-3 leading-relaxed">
                        Band is {(results.single_score as { band_basis?: string }).band_basis}.
                        A single score compares best across scenarios of the same product.
                      </p>
                    )}
                  </motion.div>
                </div>
                
                <motion.div 
                  className="w-72 h-72 flex-shrink-0"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.5, type: "spring", stiffness: 200 }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={scoreData}>
                      <RadialBar dataKey="score" cornerRadius={15} fill={scoreData[0].fill} />
                      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" className="fill-current text-3xl font-black">
                        {isMicroPoints ? singleScoreValue.toFixed(0) : `${scoreData[0].score.toFixed(1)}%`}
                      </text>
                    </RadialBarChart>
                  </ResponsiveContainer>
                </motion.div>
              </div>
              
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                className="mt-8 pt-8 border-t border-opacity-20"
              >
                <h4 className="text-xl font-bold mb-5 flex items-center">
                  <CheckCircle className="w-6 h-6 mr-2" />
                  Key Recommendations:
                </h4>
                <div className="grid md:grid-cols-3 gap-4">
                  {scoreInterpretation.recommendations.map((rec, index) => (
                    <motion.div 
                      key={index} 
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.7 + (index * 0.1) }}
                      className="flex items-start space-x-3 bg-white/40 backdrop-blur-sm rounded-xl p-4 border border-white/60"
                    >
                      <div className="w-6 h-6 bg-green-500 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                        <CheckCircle className="w-4 h-4 text-white" />
                      </div>
                      <span className="text-sm font-medium leading-relaxed">{rec}</span>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            </div>
          </motion.div>

          {/* Methodology & Weighting */}
          {results.single_score && results.single_score.weighting_factors && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mb-12"
            >
              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-8 border border-blue-200">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">
                  🔬 What drives the single score
                </h3>
                <p className="text-sm text-gray-800 mb-4 max-w-3xl">
                  Each card below is one impact category&apos;s <strong>share of the single score</strong> shown above.
                  The categories at the top are what the number is being driven by — that is where a change would move it most.
                </p>
                <p className="text-xs text-gray-600 mb-6 max-w-3xl">
                  {results.single_score.methodology}
                </p>

                {(() => {
                  // Prefer each category's actual share of the single score (what drives
                  // it); fall back to the equal weighting factors for older responses.
                  const contributions = (results.single_score as { contributions?: Record<string, number> }).contributions;
                  const entries = contributions
                    ? Object.entries(contributions).sort((a, b) => b[1] - a[1])
                    : Object.entries(results.single_score.weighting_factors);
                  const label = contributions ? 'Share of single score' : 'Weighting in final score';
                  return (
                    <div className="grid md:grid-cols-3 gap-6">
                      {entries.map(([category, frac]: [string, number]) => (
                        <div key={category} className="bg-white rounded-xl p-5 shadow-sm">
                          <h4 className="font-semibold text-gray-900 mb-2">{category}</h4>
                          <div className="text-4xl font-bold text-indigo-600 mb-2">
                            {(frac * 100).toFixed(frac < 0.1 ? 1 : 0)}%
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                            <div
                              className="bg-indigo-600 h-2 rounded-full transition-all"
                              style={{ width: `${Math.min(frac * 100, 100)}%` }}
                            />
                          </div>
                          <p className="text-xs text-gray-900">{label}</p>
                        </div>
                      ))}
                    </div>
                  );
                })()}

                <div className="mt-6 p-4 bg-white bg-opacity-60 rounded-lg border border-blue-200">
                  <p className="text-xs text-gray-900">
                    <strong>Note:</strong> This assessment follows ISO 14040/14044. The single score normalises each category
                    against a global reference set (as stated above) and combines them with <strong>equal weighting</strong> —
                    a transparent value choice applied the same way in every region, not a regional preference. Region-specific
                    adaptation is applied to the <em>inventory</em> (climate-appropriate emission factors and local grid/background
                    data), not to the normalisation or weighting.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Impact Categories Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mb-12"
          >
            <div className="bg-white rounded-2xl p-8 shadow-lg">
              <h3 className="text-2xl font-bold text-gray-900 mb-2 flex items-center">
                <BarChart3 className="w-6 h-6 text-green-600 mr-3" />
                Environmental Impact Categories
              </h3>

              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span className="text-sm text-gray-600">Functional unit:</span>
                <div className="inline-flex rounded-lg border border-gray-200 p-0.5 bg-gray-50">
                  <button
                    type="button"
                    onClick={() => setFuMode('per_kg')}
                    className={`px-3 py-1.5 text-sm font-semibold rounded-md ${fuMode === 'per_kg' ? 'bg-white shadow text-gray-900' : 'text-gray-600'}`}
                  >
                    Per kg
                  </button>
                  <button
                    type="button"
                    onClick={() => setFuMode('per_ha')}
                    disabled={!results.functional_units?.per_ha?.midpoint_impacts}
                    className={`px-3 py-1.5 text-sm font-semibold rounded-md disabled:opacity-40 ${fuMode === 'per_ha' ? 'bg-white shadow text-gray-900' : 'text-gray-600'}`}
                  >
                    Per ha
                  </button>
                </div>
                {fuMode === 'per_ha' && (
                  <span className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2 py-1">
                    Per-ha applies to the impact categories below. The single score, contribution
                    shares, and crop breakdown stay per kg (bands are calibrated per kg only).
                  </span>
                )}
              </div>
              {results.functional_units?.land_intensity_note && (
                <p className="text-sm text-gray-600 mb-4 max-w-3xl">
                  {results.functional_units.land_intensity_note}
                </p>
              )}

              {/* Whole-farm totals: per-kg figures don't change with farm size, so show the
                  total footprint too, which does scale with the farm. */}
              {(() => {
                const climateRaw = results.midpoint_impacts['Global warming'];
                const climatePerKg = isAlreadyPerKg(climateRaw)
                  ? extractValue(climateRaw)
                  : calculatePerUnitImpact(extractValue(climateRaw), totalProductionKg);
                const totalClimate = climatePerKg * totalProductionKg;
                const fmtT = totalClimate >= 1000
                  ? `${(totalClimate / 1000).toFixed(1)} t CO₂-eq`
                  : `${totalClimate.toFixed(0)} kg CO₂-eq`;
                return (
                  <div className="mb-6 flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl bg-gray-50 border border-gray-200 px-4 py-3">
                    <div className="text-sm text-gray-600">
                      Figures below are{' '}
                      <span className="font-semibold text-gray-800">
                        {fuMode === 'per_ha' ? 'per hectare of cropped area' : 'per kilogram of crop'}
                      </span>
                      {fuMode === 'per_kg'
                        ? ', so they stay the same whether the farm is large or small.'
                        : '. Land intensity (m² per kg) is separate from per-ha totals.'}
                    </div>
                    <div className="sm:ml-auto flex gap-6 text-sm">
                      <div><span className="text-gray-500">Total production: </span><span className="font-bold text-gray-900">{totalProductionKg.toLocaleString()} kg</span></div>
                      <div><span className="text-gray-500">Whole-farm climate: </span><span className="font-bold text-gray-900">{fmtT}</span></div>
                    </div>
                  </div>
                );
              })()}

              {/* Key Impact Metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                {[
                  { icon: Leaf, label: 'Climate Impact', key: 'Global warming', unit: 'kg CO₂-eq', color: 'bg-red-50 border-red-200 text-red-700' },
                  { icon: Droplets, label: 'Water Use', key: 'Water consumption', unit: 'cubic meters', color: 'bg-blue-50 border-blue-200 text-blue-700' },
                  { icon: Sun, label: 'Land Impact', key: 'Land use', unit: 'm²-years', color: 'bg-yellow-50 border-yellow-200 text-yellow-700' },
                  { icon: TreePine, label: 'Biodiversity', key: 'Biodiversity loss', unit: 'impact units', color: 'bg-green-50 border-green-200 text-green-700' },
                ].map((item, index) => {
                  const rawValue = activeMidpoints[item.key];
                  const totalValue = extractValue(rawValue);
                  const perUnitValue =
                    fuMode === 'per_ha' || isAlreadyPerKg(rawValue)
                      ? totalValue
                      : calculatePerUnitImpact(totalValue, totalProductionKg);
                  const displayValue = formatDisplayValue(perUnitValue, 1, item.key);
                  
                  return (
                    <div key={index} className={`text-center p-6 rounded-xl border-2 ${item.color}`}>
                      <item.icon className="w-10 h-10 mx-auto mb-3" />
                      <div className="text-2xl font-bold mb-1">
                        {displayValue}
                      </div>
                      <div className="text-sm font-medium opacity-75 mb-1">{item.unit} {fuUnitLabel}</div>
                      <div className="text-sm font-semibold">
                        {item.label}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Additional Impact Categories */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                {Object.entries(activeMidpoints)
                  .filter(([key]) => !['Global warming', 'Water consumption', 'Land use', 'Biodiversity loss'].includes(key))
                  .map(([category, rawValue], index) => {
                    const totalValue = extractValue(rawValue);
                    const perUnitValue =
                      fuMode === 'per_ha' || isAlreadyPerKg(rawValue)
                        ? totalValue
                        : calculatePerUnitImpact(totalValue, totalProductionKg);
                    const displayValue = formatDisplayValue(perUnitValue, 1, category);

                    return (
                      <div key={index} className="text-center p-3 bg-gray-50 rounded-lg border">
                        <div className="text-lg font-bold text-gray-900 mb-1">
                          {displayValue}
                        </div>
                        <div className="text-xs text-gray-900 leading-tight">
                          {category.replace(/([A-Z])/g, ' $1').trim()} ({fuUnitLabel})
                        </div>
                      </div>
                    );
                  })
                }
              </div>
            </div>
          </motion.div>


          {/* Crop Breakdown */}
          {Object.keys(breakdown).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  {isProcessing ? 'Impact by Product' : 'Impact by Crop'}
                </h3>

                <div className="space-y-6">
                  {Object.entries(breakdown).map(([cropName, impacts], index) => {
                    // Extract crop quantity from crop name (e.g., "Cassava (48000kg)")
                    const quantityMatch = cropName.match(/\((\d+(?:,\d+)*)kg\)/);
                    const cropQuantityKg = quantityMatch ? parseInt(quantityMatch[1].replace(/,/g, '')) : 1;
                    const cleanCropName = cropName.replace(/\s*\(\d+(?:,\d+)*kg\)/, '');
                    
                    // Headline the crop's CLIMATE footprint (a single, meaningful metric)
                    // rather than summing heterogeneous categories (kg CO2 + m2 + kg P …),
                    // which has no physical meaning. breakdown values are crop totals.
                    const climateTotal = extractValue((impacts as Record<string, unknown>)['Global warming']);
                    const climatePerKg = calculatePerUnitImpact(climateTotal, cropQuantityKg);

                    return (
                      <div key={index} className="border border-gray-200 rounded-xl p-6">
                        <div className="flex items-center justify-between mb-4">
                          <div>
                            <h4 className="text-lg font-semibold text-gray-900">{cleanCropName}</h4>
                            <p className="text-sm text-gray-800">{cropQuantityKg.toLocaleString()} kg annual production</p>
                          </div>
                          <div className="text-sm text-gray-900 text-right">
                            <div>Climate footprint: {formatDisplayValue(climatePerKg)} kg CO₂-eq per kg</div>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                          {Object.entries(impacts as Record<string, unknown>).slice(0, 4).map(([category, rawValue]) => {
                            const totalValue = extractValue(rawValue);
                            // breakdown_by_food contains total impacts per crop, need to divide by quantity
                            const perUnitValue = calculatePerUnitImpact(totalValue, cropQuantityKg);
                            const displayValue = formatDisplayValue(perUnitValue, 1, category);
                            
                            return (
                              <div key={category} className="text-center">
                                <div className="text-lg font-bold text-gray-900">
                                  {displayValue}
                                </div>
                                <div className="text-xs text-gray-900">
                                  {category.replace(/([A-Z])/g, ' $1').trim()} (per kg)
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          )}

          {/* Endpoint Impacts — only for methods that define endpoints (ReCiPe); the EF
              method is midpoint-only, so this section is hidden rather than shown empty. */}
          {results.endpoint_impacts && Object.keys(results.endpoint_impacts).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.7 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  🌍 Endpoint Impact Assessment
                </h3>
                <p className="text-gray-900 mb-6">
                  Aggregated impacts on three areas of protection (Human Health, Ecosystem Quality, Resource Scarcity)
                </p>

                <div className="grid md:grid-cols-3 gap-6">
                  {Object.entries(results.endpoint_impacts).map(([category, data]) => (
                    <div key={category} className="border border-gray-200 rounded-xl p-6 hover:border-green-500 transition-colors">
                      <h4 className="text-lg font-semibold text-gray-900 mb-2">{category}</h4>
                      <div className="text-3xl font-bold text-green-600 mb-2">
                        {formatDisplayValue(data.value, 3)}
                      </div>
                      <div className="text-sm text-gray-900 mb-4">{data.unit}</div>
                      {/* Note: EndpointResult doesn't have contributing_sources, using fallback display */}
                      {data.uncertainty_range && (
                        <div className="mt-4 pt-4 border-t">
                          <p className="text-xs font-semibold text-gray-900 mb-2">Uncertainty Range:</p>
                          <p className="text-xs text-gray-900">
                            {formatDisplayValue(data.uncertainty_range[0], 2)} - {formatDisplayValue(data.uncertainty_range[1], 2)}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}


          {/* Sensitivity Analysis */}
          {results.sensitivity_analysis && results.sensitivity_analysis.most_influential_parameters && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.9 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-300">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  🎯 Sensitivity Analysis
                </h3>
                <p className="text-gray-900 mb-6">
                  Most influential parameters affecting your environmental footprint
                </p>

                <div className="space-y-4">
                  {results.sensitivity_analysis.most_influential_parameters.map((param, idx: number) => (
                    <div key={idx} className="border border-gray-200 rounded-xl p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h4 className="text-lg font-semibold text-gray-900">{param.parameter_name}</h4>
                          <p className="text-sm text-gray-900">Influence on total impact: <span className="font-bold text-blue-600 text-lg">{param.influence_percentage.toFixed(1)}%</span></p>
                        </div>
                        <div className="text-right">
                          <div className="text-3xl font-bold text-green-600">{param.improvement_potential}%</div>
                          <div className="text-sm font-medium text-gray-900">Improvement potential</div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-gray-900 font-medium">Current Uncertainty:</span>
                          <div className="font-bold text-gray-900 text-lg mt-1">
                            {param.current_uncertainty ? `±${param.current_uncertainty}%` : 'N/A'}
                          </div>
                        </div>
                        <div>
                          <span className="text-gray-900 font-medium">Impact Influence:</span>
                          <div className="font-bold text-blue-600 text-lg mt-1">
                            {param.influence_percentage ? `${param.influence_percentage.toFixed(1)}%` : 'N/A'}
                          </div>
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="w-full bg-gray-200 rounded-full h-3">
                          <div
                            className="bg-gradient-to-r from-green-400 to-green-600 h-3 rounded-full transition-all"
                            style={{ width: `${param.influence_percentage}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

              </div>
            </motion.div>
          )}

          {/* Scenario Analysis (from sensitivity analysis) */}
          {results.sensitivity_analysis?.scenario_analysis && results.sensitivity_analysis.scenario_analysis.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.95 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  📈 What-If Scenario Analysis
                </h3>
                <p className="text-gray-900 mb-6">
                  Explore potential improvements by adopting different farming practices and technologies
                </p>

                <div className="grid md:grid-cols-2 gap-6">
                  {results.sensitivity_analysis.scenario_analysis.map((scenario, idx: number) => (
                    <div key={idx} className="border-2 border-gray-200 rounded-xl p-6 hover:border-green-500 transition-all hover:shadow-lg">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h4 className="text-lg font-semibold text-gray-900 mb-1">{scenario.scenario_name}</h4>
                          <p className="text-sm text-gray-900">{scenario.description}</p>
                        </div>
                        <ArrowRight className="w-6 h-6 text-green-600 flex-shrink-0" />
                      </div>

                      <div className="space-y-3">
                        <h5 className="font-semibold text-gray-900 text-sm">Expected Impact Changes:</h5>
                        {Object.entries(scenario.impact_changes).map(([category, change]: [string, number]) => (
                          <div key={category} className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
                            <span className="text-sm text-gray-900">{category}</span>
                            <div className="flex items-center space-x-2">
                              <span className={`text-lg font-bold ${change < 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {change > 0 ? '+' : ''}{change}%
                              </span>
                              {change < 0 ? (
                                <CheckCircle className="w-5 h-5 text-green-600" />
                              ) : (
                                <AlertTriangle className="w-5 h-5 text-red-600" />
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Comparative Analysis */}
          {results.comparative_analysis && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.0 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-300">
                <h3 className="text-2xl font-bold text-gray-900 mb-6">
                  📊 Comparative Analysis
                </h3>

                {/* Benchmark Comparisons */}
                {results.comparative_analysis.benchmark_comparisons && results.comparative_analysis.benchmark_comparisons.length > 0 && (
                  <div className="mb-8">
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">Benchmark Comparisons</h4>
                    <div className="space-y-4">
                      {results.comparative_analysis.benchmark_comparisons.map((benchmark, idx: number) => (
                        <div key={idx} className="border border-gray-200 rounded-xl p-6">
                          <div className="flex items-center justify-between mb-3">
                            <span className="font-semibold text-gray-900">{benchmark.benchmark_name}</span>
                            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                              benchmark.performance_category === 'Excellent' ? 'bg-green-100 text-green-800' :
                              benchmark.performance_category === 'Good' ? 'bg-blue-100 text-blue-800' :
                              benchmark.performance_category === 'Average' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-orange-100 text-orange-800'
                            }`}>
                              {benchmark.performance_category}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                              <div className="text-gray-900">Your Performance</div>
                              <div className="font-bold text-gray-900 text-lg">{formatDisplayValue(benchmark.your_performance, 2)}</div>
                            </div>
                            <div>
                              <div className="text-gray-900">Benchmark Value</div>
                              <div className="font-bold text-gray-900 text-lg">{formatDisplayValue(benchmark.benchmark_value, 2)}</div>
                            </div>
                            <div>
                              <div className="text-gray-900">Difference</div>
                              <div className="font-bold text-green-600 text-lg">{formatDisplayValue(benchmark.percentage_difference, 1)}%</div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Regional Comparisons */}
                {results.comparative_analysis.regional_comparisons && results.comparative_analysis.regional_comparisons.length > 0 && (
                  <div className="mb-8">
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">Regional Comparisons</h4>
                    <div className="space-y-4">
                      {results.comparative_analysis.regional_comparisons.map((regional, idx: number) => (
                        <div key={idx} className="border border-gray-200 rounded-xl p-6">
                          <div className="mb-3">
                            <span className="font-semibold text-gray-900">{regional.region_name}</span>
                          </div>
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            {Object.entries(regional.impact_ratios).map(([impact, ratio]: [string, number]) => (
                              <div key={impact} className="mb-2">
                                <div className="text-gray-900 font-medium">{impact}</div>
                                <div className="font-bold text-gray-900 text-lg">{formatDisplayValue(ratio, 2)}x regional average</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Best Practices */}
                {results.comparative_analysis.best_practices && results.comparative_analysis.best_practices.length > 0 && (
                  <div>
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">🌟 Best Practices for Improvement</h4>
                    <div className="grid md:grid-cols-2 gap-4">
                      {results.comparative_analysis.best_practices.map((practice, idx: number) => (
                        <div key={idx} className="border-2 border-green-500 bg-white rounded-xl p-5 shadow-sm">
                          <div className="flex items-start space-x-3">
                            <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                            <div>
                              <h5 className="font-semibold text-gray-900 mb-1">{practice.practice_name}</h5>
                              <p className="text-sm text-gray-900 mb-2">{practice.description}</p>
                              <div className="flex items-center space-x-4 text-xs">
                                <span className="text-green-700 font-semibold">
                                  Impact reduction potential available
                                </span>
                                <span className="text-gray-900">
                                  Implementation: {practice.implementation_difficulty}
                                </span>
                                <span className="text-gray-900">
                                  Cost: {practice.cost_category}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* What this means for your farm — interactive plain-language chat */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 1.05 }}
            className="mb-12"
          >
            <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50/70 to-white p-6 md:p-8">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                What this means for your farm
              </h2>
              <p className="text-gray-600 mb-5 max-w-2xl">
                Get a plain-language summary of your results and ask any questions about them.
                The answers are based only on this assessment. The technical ISO draft is below.
              </p>
              <button
                type="button"
                onClick={() => setChatOpen(true)}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 text-white font-semibold shadow-sm hover:bg-emerald-700 transition-colors"
              >
                <Leaf className="w-5 h-5" />
                Plain-language summary
              </button>
            </div>
          </motion.div>

          {/* Practical, costed, sequenced recommendations (deterministic engine) */}
          {assessmentId && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.05 }}
              className="mb-12"
            >
              <RecommendationsPanel assessmentId={assessmentId} isProcessing={isProcessing} />
            </motion.div>
          )}

          {/* Researcher: scenarios, method, uncertainty */}
          {assessmentId && !isProcessing && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.06 }}
              className="mb-12"
            >
              <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 space-y-6">
                {panelError && (
                  <div
                    role="alert"
                    aria-live="assertive"
                    className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
                  >
                    {panelError}
                  </div>
                )}
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-1">Compare scenario</h3>
                  <p className="text-sm text-gray-600 mb-3">
                    Re-solve from the archived request with a named patch (not a static tip card).
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      disabled={scenarioBusy}
                      className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      onClick={() => runScenario({ name: 'Yield +20%', yield_scale: 1.2 })}
                    >
                      Yield +20%
                    </button>
                    <button
                      type="button"
                      disabled={scenarioBusy}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-800 disabled:opacity-50"
                      onClick={() => runScenario({ name: 'N −20%', n_rate_scale: 0.8 })}
                    >
                      N −20%
                    </button>
                    <button
                      type="button"
                      disabled={scenarioBusy}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-800 disabled:opacity-50"
                      onClick={() => runScenario({ name: 'Fuel −30%', diesel_scale: 0.7 })}
                    >
                      Fuel −30%
                    </button>
                    {scenarioBusy && <span className="text-xs text-gray-500">Re-solving…</span>}
                    {scenarioDeltas.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setScenarioDeltas([])}
                        className="ml-auto text-xs font-semibold text-gray-500 hover:text-gray-800 hover:underline"
                      >
                        Clear ({scenarioDeltas.length})
                      </button>
                    )}
                  </div>
                  {scenarioDeltas.length > 0 && (
                    <div className="mt-4 space-y-3">
                      <p className="text-xs text-gray-500">
                        Each bar is a category&apos;s % change vs baseline (a tornado of
                        sensitivities). Run several scenarios to compare them.
                      </p>
                      {scenarioDeltas.map((s) => (
                        <ScenarioTornado
                          key={s.scenario_id}
                          delta={s}
                          baselineSingleScore={singleScoreValue}
                        />
                      ))}
                    </div>
                  )}
                </div>

                <div className="border-t border-gray-100 pt-4">
                  <h3 className="text-lg font-bold text-gray-900 mb-1">LCIA method</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    Active:{' '}
                    <span className="font-semibold text-gray-800">
                      {results.lcia_method ||
                        (typeof results.single_score === 'object' && results.single_score?.methodology) ||
                        'Region default'}
                    </span>
                  </p>
                  <div className="flex flex-wrap gap-2 items-center">
                    <select
                      aria-label="Switch LCIA characterization method"
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      disabled={methodBusy}
                      defaultValue=""
                      onChange={(e) => {
                        if (e.target.value) runRecharacterize(e.target.value);
                      }}
                    >
                      <option value="" disabled>
                        Switch method…
                      </option>
                      <option value="ReCiPe 2016 v1.03, midpoint (H)">
                        ReCiPe 2016 v1.03, midpoint (H)
                      </option>
                      <option value="EF v3.1">EF v3.1</option>
                    </select>
                    {methodBusy && (
                      <span className="text-xs text-gray-500">Recharacterizing…</span>
                    )}
                    {results.method_variants && Object.keys(results.method_variants).length > 0 && (
                      <span className="text-xs text-gray-500">
                        Cached variants: {Object.keys(results.method_variants).join(', ')}
                      </span>
                    )}
                  </div>

                  {(() => {
                    const primaryMethod =
                      results.lcia_method ||
                      (typeof results.single_score === 'object' && results.single_score?.methodology) ||
                      'Primary';
                    const columns: { key: string; label: string; midpoints: AssessmentResult['midpoint_impacts'] }[] = [
                      { key: 'primary', label: String(primaryMethod), midpoints: results.midpoint_impacts },
                    ];
                    if (results.method_variants) {
                      for (const [methodName, block] of Object.entries(results.method_variants)) {
                        if (block?.midpoint_impacts && methodName !== results.lcia_method) {
                          columns.push({
                            key: methodName,
                            label: methodName,
                            midpoints: block.midpoint_impacts as AssessmentResult['midpoint_impacts'],
                          });
                        }
                      }
                    }
                    if (columns.length < 2) return null;
                    const categories = Array.from(
                      new Set(columns.flatMap((c) => Object.keys(c.midpoints || {})))
                    ).sort();
                    const readVal = (raw: unknown) =>
                      typeof raw === 'object' && raw !== null && 'value' in raw
                        ? (raw as { value: number; unit?: string })
                        : { value: typeof raw === 'number' ? raw : 0, unit: '' };
                    return (
                      <div className="mt-4 overflow-x-auto">
                        <p className="text-sm font-semibold text-gray-900 mb-2">
                          Side-by-side midpoints (per kg)
                        </p>
                        <table className="min-w-full text-sm text-left">
                          <thead className="text-gray-500 border-b">
                            <tr>
                              <th className="py-1 pr-3">Category</th>
                              {columns.map((c) => (
                                <th key={c.key} className="py-1 pr-3 max-w-[12rem] align-bottom" title={c.label}>
                                  <span className="block truncate">{c.label}</span>
                                  {c.key !== 'primary' && (
                                    <button
                                      type="button"
                                      disabled={methodBusy}
                                      onClick={() => runRecharacterize(c.key, true)}
                                      className="mt-1 text-xs font-normal text-green-700 hover:text-green-900 hover:underline disabled:opacity-50"
                                    >
                                      Set as primary
                                    </button>
                                  )}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {categories.map((cat) => (
                              <tr key={cat} className="border-b border-gray-100">
                                <td className="py-1 pr-3 font-medium text-gray-900">{cat}</td>
                                {columns.map((c) => {
                                  const cell = readVal(c.midpoints?.[cat]);
                                  return (
                                    <td key={c.key} className="py-1 pr-3 font-mono text-gray-700">
                                      {formatDisplayValue(cell.value, 2, cat)}
                                      {cell.unit ? (
                                        <span className="text-xs text-gray-500 ml-1">{cell.unit}</span>
                                      ) : null}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    );
                  })()}
                </div>

                <div className="border-t border-gray-100 pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                    <h3 className="text-lg font-bold text-gray-900">Uncertainty (pedigree MC)</h3>
                    <button
                      type="button"
                      onClick={runUncertainty}
                      disabled={mcBusy}
                      aria-busy={mcBusy}
                      className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-semibold text-gray-800 hover:bg-gray-50 disabled:opacity-50"
                    >
                      {mcBusy ? 'Running Monte Carlo…' : results.uncertainty?.n ? 'Refresh MC' : 'Run MC'}
                    </button>
                  </div>
                  <p className="text-sm text-gray-600">
                    {results.uncertainty?.n
                      ? `Per-source pedigree-matrix Monte Carlo ran with this assessment (N=${results.uncertainty.n}${results.uncertainty.gsd ? `, study GSD ${results.uncertainty.gsd.toFixed(2)}` : ''}). Each source is scored on the ecoinvent pedigree matrix for its own geometric SD, sampled independently. Characterization-factor uncertainty is not propagated at this screening level.`
                      : 'This saved result has no Monte Carlo block yet. Run MC to attach p5–p95 confidence intervals to every impact category and the single score.'}
                  </p>

                  {results.uncertainty?.gsd_by_source &&
                    Object.keys(results.uncertainty.gsd_by_source).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(results.uncertainty.gsd_by_source)
                          .sort((a, b) => b[1] - a[1])
                          .map(([src, g]) => (
                            <span
                              key={src}
                              className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-600"
                              title={`Geometric standard deviation for ${src}`}
                            >
                              <span className="truncate max-w-[14rem]">{src}</span>
                              <span className="font-mono text-gray-500">GSD {g.toFixed(2)}</span>
                            </span>
                          ))}
                      </div>
                    )}

                  {results.uncertainty?.single_score && (
                    <p className="mt-2 text-sm text-gray-700">
                      <span className="font-semibold">Single score p5–p95:</span>{' '}
                      <span className="font-mono">
                        {results.uncertainty.single_score.p5.toFixed(1)} –{' '}
                        {results.uncertainty.single_score.p95.toFixed(1)}
                      </span>{' '}
                      <span className="text-gray-500">
                        (median {results.uncertainty.single_score.p50.toFixed(1)}{' '}
                        {(results.single_score as SingleScoreResult)?.unit || 'µPt per kg'})
                      </span>
                    </p>
                  )}

                  {results.uncertainty?.percentiles &&
                    Object.keys(results.uncertainty.percentiles).length > 0 && (
                      <div className="mt-3 overflow-x-auto">
                        <table className="min-w-full text-sm text-left">
                          <caption className="sr-only">
                            Monte Carlo p5, base, and p95 per impact category
                          </caption>
                          <thead className="text-gray-500 border-b">
                            <tr>
                              <th scope="col" className="py-1 pr-3">Category</th>
                              <th scope="col" className="py-1 pr-3 text-right">p5</th>
                              <th scope="col" className="py-1 pr-3 text-right">Base</th>
                              <th scope="col" className="py-1 pr-3 text-right">p95</th>
                              <th scope="col" className="py-1 pr-3 text-right">± range</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(results.uncertainty.percentiles).map(([cat, p]) => {
                              const base = p.base ?? p.p50;
                              const spread = base ? ((p.p95 - p.p5) / (2 * base)) * 100 : null;
                              return (
                                <tr key={cat} className="border-b border-gray-100">
                                  <td className="py-1 pr-3 font-medium text-gray-900">{cat}</td>
                                  <td className="py-1 pr-3 text-right font-mono text-gray-700">
                                    {formatDisplayValue(p.p5, 2, cat)}
                                  </td>
                                  <td className="py-1 pr-3 text-right font-mono text-gray-900">
                                    {formatDisplayValue(base, 2, cat)}
                                  </td>
                                  <td className="py-1 pr-3 text-right font-mono text-gray-700">
                                    {formatDisplayValue(p.p95, 2, cat)}
                                  </td>
                                  <td className="py-1 pr-3 text-right font-mono text-gray-500">
                                    {spread != null ? `±${spread.toFixed(0)}%` : 'n/a'}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                </div>

                {results.contribution_sankey?.categories && (
                  <div className="border-t border-gray-100 pt-4">
                    <h3 className="text-lg font-bold text-gray-900 mb-1">Top sources (GWP & land)</h3>
                    <p className="text-sm text-gray-600 mb-3">
                      Ranked from contribution_by_source. Shares are ratios, so they are the
                      same per kg and per hectare (the functional-unit toggle does not change them).
                    </p>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {Object.entries(results.contribution_sankey.categories).map(([cat, block]) => (
                        <div key={cat} className="rounded-lg border border-gray-200 p-3">
                          <p className="font-semibold text-gray-900 mb-2">{cat}</p>
                          <ul className="space-y-1 text-sm">
                            {(block.sources ?? []).map((row) => (
                              <li key={row.source} className="flex justify-between gap-2">
                                <span className="text-gray-700 truncate" title={row.source}>
                                  {row.rank}. {row.source}
                                </span>
                                <span className="font-mono text-gray-600 shrink-0">
                                  {(row.share * 100).toFixed(0)}%
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* LCI / match transparency + research export */}
          {assessmentId && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.08 }}
              className="mb-12"
            >
              <details className="bg-white rounded-2xl shadow-lg border border-gray-200">
                <summary className="cursor-pointer p-6 text-xl font-bold text-gray-900 list-none flex items-center justify-between">
                  <span>LCI matches &amp; research export</span>
                  <span className="text-sm font-normal text-gray-500">Click to expand</span>
                </summary>
                <div className="px-6 pb-6 border-t border-gray-100 space-y-4">
                  <p className="text-sm text-gray-600 pt-4">
                    Background processes matched for this study, with amounts and whether the
                    input was estimated. Download the full study JSON, or a tidy per-table CSV
                    (one rectangular table, loadable in a single pandas/R read_csv).
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      disabled={exportBusy !== null}
                      aria-busy={exportBusy === 'json'}
                      className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800 disabled:opacity-50"
                      onClick={() => runExport('json')}
                    >
                      {exportBusy === 'json' ? 'Preparing JSON…' : 'Download JSON'}
                    </button>
                    {(['impacts', 'matches', 'contributions'] as const).map((sec) => (
                      <button
                        key={sec}
                        type="button"
                        disabled={exportBusy !== null}
                        aria-busy={exportBusy === `csv:${sec}`}
                        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-800 hover:bg-gray-50 disabled:opacity-50"
                        onClick={() => runExport('csv', sec)}
                      >
                        {exportBusy === `csv:${sec}`
                          ? 'Preparing…'
                          : `CSV: ${sec}`}
                      </button>
                    ))}
                  </div>
                  {results.provenance && (
                    <p className="text-xs text-gray-500">
                      <span className="font-semibold text-gray-600">Provenance:</span>{' '}
                      {results.provenance.engine}
                      {results.provenance.engine_version ? ` v${results.provenance.engine_version}` : ''}
                      {results.provenance.lcia_method ? ` · ${results.provenance.lcia_method}` : ''}
                      {results.provenance.field_emission_model ? ` · ${results.provenance.field_emission_model}` : ''}
                      {results.provenance.background_databases?.length
                        ? ` · ${results.provenance.background_databases
                            .map((d) => `${d.name ?? ''} ${d.version ?? ''}`.trim())
                            .filter(Boolean)
                            .join(', ')}`
                        : ''}
                    </p>
                  )}
                  {panelError && (
                    <div
                      role="alert"
                      aria-live="assertive"
                      className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700"
                    >
                      {panelError}
                    </div>
                  )}
                  {Array.isArray((results as { input_matches?: unknown[] }).input_matches) &&
                  ((results as { input_matches: unknown[] }).input_matches?.length ?? 0) > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm text-left">
                        <thead className="text-gray-500 border-b">
                          <tr>
                            <th className="py-2 pr-3">Input</th>
                            <th className="py-2 pr-3">Amount</th>
                            <th className="py-2 pr-3">Matched process</th>
                            <th className="py-2 pr-3">Score</th>
                            <th className="py-2">Estimated</th>
                          </tr>
                        </thead>
                        <tbody>
                          {((results as {
                            input_matches: Array<{
                              input?: string;
                              name?: string;
                              amount?: number;
                              amount_unit?: string;
                              unit?: string;
                              matched?: string | { name?: string };
                              score?: number;
                              estimated?: boolean;
                            }>;
                          }).input_matches).map((m, i) => {
                            const matched =
                              typeof m.matched === 'object' && m.matched
                                ? m.matched.name
                                : m.matched;
                            return (
                              <tr key={i} className="border-b border-gray-100">
                                <td className="py-2 pr-3 font-medium text-gray-900">
                                  {m.input || m.name || '—'}
                                </td>
                                <td className="py-2 pr-3 text-gray-700">
                                  {m.amount != null
                                    ? `${m.amount} ${m.amount_unit || m.unit || ''}`.trim()
                                    : '—'}
                                </td>
                                <td className="py-2 pr-3 text-gray-700 max-w-md truncate" title={matched || ''}>
                                  {matched || '—'}
                                </td>
                                <td className="py-2 pr-3 text-gray-700">
                                  {m.score != null ? m.score.toFixed(3) : '—'}
                                </td>
                                <td className="py-2 text-gray-700">{m.estimated ? 'Yes' : 'No'}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">
                      No input-match rows on this saved result (older assessments may omit them).
                    </p>
                  )}
                </div>
              </details>
            </motion.div>
          )}

          {/* Technical report (ISO 14044 draft) — collapsed by default */}
          {(results as { iso_report?: unknown }).iso_report ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1.1 }}
              className="mb-12"
            >
              <details className="bg-white rounded-2xl shadow-lg border border-gray-200">
                <summary className="cursor-pointer p-6 text-xl font-bold text-gray-900 list-none flex items-center justify-between">
                  <span>Technical report (ISO 14044 draft)</span>
                  <span className="text-sm font-normal text-gray-500">Click to expand</span>
                </summary>
                <div className="px-6 pb-6 border-t border-gray-100">
                  <ISOReport report={(results as { iso_report?: Parameters<typeof ISOReport>[0]['report'] }).iso_report} />
                </div>
              </details>
            </motion.div>
          ) : null}

          {/* Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 1.2 }}
            className="text-center"
          >
            <div className="bg-gradient-to-r from-green-600 to-emerald-600 rounded-2xl p-8 text-white">
              <h3 className="text-2xl font-bold mb-4">Take Action on Your Results</h3>
              <p className="text-green-100 mb-6 max-w-2xl mx-auto">
                Use these insights to improve your farm&apos;s sustainability and productivity
              </p>
              
              <div className="flex flex-col sm:flex-row gap-4 justify-center flex-wrap">
                {canRerun && (
                  <button
                    type="button"
                    onClick={() => setPendingRerun(true)}
                    disabled={!assessmentId || actionBusy}
                    className="bg-white text-green-600 px-6 py-3 rounded-xl font-semibold hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-all"
                  >
                    <Pencil className="w-5 h-5" />
                    <span>Update &amp; re-run</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleDownload}
                  className="border-2 border-white text-white px-6 py-3 rounded-xl font-semibold hover:bg-white hover:text-green-600 flex items-center space-x-2 transition-colors"
                >
                  <Download className="w-5 h-5" />
                  <span>Download Report</span>
                </button>

                <button
                  type="button"
                  onClick={() => setPendingDelete(true)}
                  disabled={!assessmentId || actionBusy}
                  className="border-2 border-red-200 bg-red-50/10 text-white px-6 py-3 rounded-xl font-semibold hover:bg-red-600 flex items-center space-x-2 transition-colors disabled:opacity-50"
                >
                  <Trash2 className="w-5 h-5" />
                  <span>Delete</span>
                </button>

                <button
                  type="button"
                  onClick={handleShare}
                  className="border-2 border-white text-white px-6 py-3 rounded-xl font-semibold hover:bg-white hover:text-green-600 flex items-center space-x-2 transition-colors"
                >
                  <Share className="w-5 h-5" />
                  <span>{shareLabel}</span>
                </button>

                <a
                  href="/dashboard"
                  className="border-2 border-white text-white px-6 py-3 rounded-xl font-semibold hover:bg-white hover:text-green-600 flex items-center space-x-2 transition-colors"
                >
                  <BarChart3 className="w-5 h-5" />
                  <span>Back to dashboard</span>
                </a>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      <ResultsChat
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        assessmentData={results}
        assessmentId={assessmentId}
      />

      <ConfirmDialog
        open={pendingDelete}
        title="Delete this assessment?"
        description={
          <>
            This permanently removes <strong>{displayName}</strong> and its scores, ISO draft,
            and chat grounding. This cannot be undone.
          </>
        }
        confirmLabel="Delete assessment"
        requireText={String(displayName)}
        busy={actionBusy}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(false)}
      />

      <ConfirmDialog
        open={pendingRerun}
        title="Update and re-run?"
        description={
          <>
            Change the inputs for <strong>{displayName}</strong>. When you submit, the existing
            scores and report will be <strong>replaced</strong> — the assessment id stays the same.
          </>
        }
        confirmLabel="Continue to editor"
        tone="warning"
        onConfirm={confirmRerun}
        onCancel={() => setPendingRerun(false)}
      />
    </Layout>
  );
}

export default function ResultsPage() {
  return (
    <RequireAuth>
      <Suspense fallback={
        <Layout>
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="text-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                className="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full mx-auto mb-4"
              />
              <p className="text-lg text-gray-900">Loading...</p>
            </div>
          </div>
        </Layout>
      }>
        <ResultsPageContent />
      </Suspense>
    </RequireAuth>
  );
}

function ResultsPageContent() {
  const searchParams = useSearchParams();
  const assessmentId = searchParams.get('id');
  const isProcessing = searchParams.get('type') === 'processing';

  return <ResultsContent assessmentId={assessmentId} isProcessing={isProcessing} />;
}