'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Sprout, Factory, FileBarChart, Loader2, Gauge, MapPin } from 'lucide-react';
import RequireAuth from '@/components/RequireAuth';
import DashboardShell from '@/components/DashboardShell';
import NewAssessmentButton from '@/components/NewAssessmentButton';
import DashboardRecommendations from '@/components/DashboardRecommendations';
import { useAuth } from '@/contexts/AuthContext';
import { assessmentAPI, AssessmentSummary, Facility, Farm } from '@/lib/api';

export const dynamic = 'force-dynamic';

function OverviewContent() {
  const { user } = useAuth();
  const isProcessor = user?.role === 'processor';
  const isOfficer = user?.role === 'extension_officer';
  const isResearcher = user?.role === 'researcher';
  // Only owners keep a farm/facility registry; officers/researchers assess via the wizard.
  const showFarms = user?.role === 'farmer';
  const showFacilities = isProcessor;

  const [assessments, setAssessments] = useState<AssessmentSummary[]>([]);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const tasks: Promise<unknown>[] = [assessmentAPI.getMyAssessments()];
        if (showFarms) tasks.push(assessmentAPI.getFarms());
        if (showFacilities) tasks.push(assessmentAPI.getFacilities());

        const results = await Promise.all(tasks);
        if (!active) return;

        setAssessments((results[0] as { assessments: AssessmentSummary[] }).assessments);
        let idx = 1;
        if (showFarms) {
          setFarms(results[idx] as Farm[]);
          idx += 1;
        }
        if (showFacilities) {
          setFacilities(results[idx] as Facility[]);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load your dashboard.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [showFarms, showFacilities]);

  const managedCount = showFacilities ? facilities.length : showFarms ? farms.length : null;

  const scored = assessments.filter((a) => typeof a.single_score === 'number');
  // Lower single score = better footprint; averaging across crops/regions is misleading.
  const bestScore =
    scored.length > 0 ? Math.min(...scored.map((a) => a.single_score as number)) : null;
  const worstScore =
    scored.length > 0 ? Math.max(...scored.map((a) => a.single_score as number)) : null;
  const bestAssessment =
    bestScore !== null ? scored.find((a) => a.single_score === bestScore) : undefined;
  const bestLabel = bestAssessment?.title || bestAssessment?.company_name;
  const scoreHint =
    bestScore === null
      ? undefined
      : [
          'Lowest is better',
          worstScore !== null && worstScore !== bestScore
            ? `Worst ${worstScore.toFixed(3)}`
            : null,
          bestLabel ? `Best: ${bestLabel}` : null,
        ]
          .filter(Boolean)
          .join(' · ');

  const managedLabel = isProcessor ? 'Facilities' : 'Farms';
  const showManagedStat = showFarms || showFacilities;

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Welcome back, {user?.full_name?.split(' ')[0] || 'there'}
          </h2>
          <p className="text-gray-600">
            {isResearcher
              ? 'Run farm and processing assessments for study — without owning site profiles.'
              : isOfficer
                ? 'Run farm assessments for the growers you support — enter their details in the wizard.'
                : isProcessor
                  ? 'Measure and improve your facilities’ footprint.'
                  : 'Measure and improve your farm’s footprint.'}
          </p>
        </div>
        <NewAssessmentButton />
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {/* Stats */}
      <div className={`grid gap-4 ${showManagedStat ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
        {showManagedStat && (
          <StatCard
            icon={isProcessor ? Factory : Sprout}
            label={managedLabel}
            value={loading ? '—' : managedCount ?? 0}
            href={isProcessor ? '/dashboard/facilities' : '/dashboard/farms'}
          />
        )}
        <StatCard
          icon={FileBarChart}
          label="Saved assessments"
          value={loading ? '—' : assessments.length}
          href="/dashboard/assessments"
        />
        <StatCard
          icon={Gauge}
          label="Best single score"
          value={loading ? '—' : bestScore !== null ? bestScore.toFixed(3) : '—'}
          hint={loading ? undefined : scoreHint}
        />
      </div>

      {/* Recommended next steps for the most recent assessment */}
      {!loading && assessments.length > 0 && (
        <DashboardRecommendations assessment={assessments[0]} />
      )}

      {/* Role-aware profiles */}
      {(showFarms || showFacilities) && (
        <section className="space-y-6">
          {showFarms && (
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">Your farms</h3>
                <Link href="/dashboard/farms" className="text-sm font-medium text-moss hover:text-spruce">
                  Manage
                </Link>
              </div>
              {loading ? (
                <div className="mt-4 flex items-center gap-2 text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading…
                </div>
              ) : farms.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-8 text-center text-sm text-gray-600">
                  No farms yet.{' '}
                  <Link href="/dashboard/farms" className="font-medium text-moss hover:text-spruce">
                    Add a farm
                  </Link>
                </div>
              ) : (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {farms.slice(0, 6).map((farm) => (
                    <Link
                      key={farm.id}
                      href={`/dashboard/farms/${farm.id}`}
                      className="rounded-2xl border border-gray-200 bg-white p-4 hover:border-moss/40 hover:bg-moss/5 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div className="rounded-lg bg-moss/10 p-2 text-spruce">
                          <Sprout className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-medium text-gray-900 truncate">{farm.name}</div>
                          {(farm.location || farm.country) && (
                            <p className="mt-0.5 flex items-center gap-1 text-xs text-gray-500">
                              <MapPin className="w-3 h-3 shrink-0" />
                              <span className="truncate">
                                {[farm.location, farm.region, farm.country].filter(Boolean).join(', ')}
                              </span>
                            </p>
                          )}
                          {farm.farmer_name && (
                            <p className="mt-1 text-xs text-gray-500 truncate">{farm.farmer_name}</p>
                          )}
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {showFacilities && (
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">Your facilities</h3>
                <Link
                  href="/dashboard/facilities"
                  className="text-sm font-medium text-moss hover:text-spruce"
                >
                  Manage
                </Link>
              </div>
              {loading ? (
                <div className="mt-4 flex items-center gap-2 text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading…
                </div>
              ) : facilities.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-8 text-center text-sm text-gray-600">
                  No facilities yet.{' '}
                  <Link href="/dashboard/facilities" className="font-medium text-moss hover:text-spruce">
                    Add a facility
                  </Link>
                </div>
              ) : (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {facilities.slice(0, 6).map((facility) => (
                    <Link
                      key={facility.id}
                      href={`/dashboard/facilities/${facility.id}`}
                      className="rounded-2xl border border-gray-200 bg-white p-4 hover:border-moss/40 hover:bg-moss/5 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div className="rounded-lg bg-moss/10 p-2 text-spruce">
                          <Factory className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-medium text-gray-900 truncate">{facility.name}</div>
                          <p className="mt-0.5 text-xs text-gray-500">{facility.facility_type || 'Facility'}</p>
                          {(facility.location || facility.country) && (
                            <p className="mt-0.5 flex items-center gap-1 text-xs text-gray-500">
                              <MapPin className="w-3 h-3 shrink-0" />
                              <span className="truncate">
                                {[facility.location, facility.region, facility.country]
                                  .filter(Boolean)
                                  .join(', ')}
                              </span>
                            </p>
                          )}
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Recent assessments */}
      <section>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Recent assessments</h3>
          <Link href="/dashboard/assessments" className="text-sm font-medium text-moss hover:text-spruce">
            View all
          </Link>
        </div>

        {loading ? (
          <div className="mt-4 flex items-center gap-2 text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </div>
        ) : assessments.length === 0 ? (
          <div className="mt-4 rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-10 text-center">
            <p className="text-gray-600">No assessments yet.</p>
            <div className="mt-4 flex justify-center">
              <NewAssessmentButton label="Run your first assessment" />
            </div>
          </div>
        ) : (
          <div className="mt-4 overflow-hidden rounded-2xl border border-gray-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Assessment</th>
                  <th className="px-4 py-3 font-medium hidden sm:table-cell">Type</th>
                  <th className="px-4 py-3 font-medium hidden md:table-cell">Date</th>
                  <th className="px-4 py-3 font-medium">Score</th>
                  <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {assessments.slice(0, 5).map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{a.title || a.company_name || 'Untitled'}</div>
                      <div className="text-gray-400">{a.country}</div>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell capitalize text-gray-600">{a.type}</td>
                    <td className="px-4 py-3 hidden md:table-cell text-gray-600">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-900">
                      {typeof a.single_score === 'number' ? a.single_score.toFixed(3) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/results?id=${a.id}${a.type === 'processing' ? '&type=processing' : ''}`}
                        className="font-medium text-moss hover:text-spruce"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  href,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  hint?: string;
  href?: string;
}) {
  const inner = (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        <Icon className="w-5 h-5 text-moss" />
      </div>
      <div className="mt-2 text-3xl font-bold text-gray-900">{value}</div>
      {hint && <p className="mt-1 text-xs text-gray-500 leading-snug">{hint}</p>}
    </div>
  );
  return href ? (
    <Link href={href} className="block hover:opacity-90 transition-opacity">
      {inner}
    </Link>
  ) : (
    inner
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardShell active="overview" title="Dashboard">
        <OverviewContent />
      </DashboardShell>
    </RequireAuth>
  );
}
