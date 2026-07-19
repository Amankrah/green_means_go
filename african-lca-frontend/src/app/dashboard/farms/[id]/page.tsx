'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Loader2,
  MapPin,
  Pencil,
  Sprout,
  Trash2,
  User,
  Ruler,
  StickyNote,
  Phone,
  FileBarChart,
} from 'lucide-react';
import RequireAuth from '@/components/RequireAuth';
import DashboardShell from '@/components/DashboardShell';
import ConfirmDialog from '@/components/ConfirmDialog';
import FarmCropSummary from '@/components/FarmCropSummary';
import { assessmentAPI, AssessmentSummary, Farm } from '@/lib/api';
import { normalizeFarmSnapshot, type FarmSnapshot } from '@/lib/farm-snapshot';

export const dynamic = 'force-dynamic';

function FarmProfileContent() {
  const params = useParams();
  const router = useRouter();
  const farmId = typeof params.id === 'string' ? params.id : '';

  const [farm, setFarm] = useState<Farm | null>(null);
  const [assessments, setAssessments] = useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<FarmSnapshot | null>(null);
  const [snapshotSource, setSnapshotSource] = useState<AssessmentSummary | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  useEffect(() => {
    if (!farmId) return;
    let active = true;
    (async () => {
      try {
        const [f, a] = await Promise.all([
          assessmentAPI.getFarm(farmId),
          assessmentAPI.getMyAssessments(),
        ]);
        if (!active) return;
        setFarm(f);
        setAssessments(a.assessments.filter((row) => row.farm_id === farmId));
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load this farm.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [farmId]);

  const latestRerunnable = useMemo(() => {
    return [...assessments]
      .filter((a) => a.can_rerun)
      .sort((a, b) => {
        const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
        const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
        return tb - ta;
      })[0] ?? null;
  }, [assessments]);

  useEffect(() => {
    if (loading || !farm) return;

    if (assessments.length === 0 || !latestRerunnable) {
      setSnapshot(null);
      setSnapshotSource(null);
      setSnapshotError(null);
      setSnapshotLoading(false);
      return;
    }

    let active = true;
    setSnapshotLoading(true);
    setSnapshotError(null);
    (async () => {
      try {
        const archive = await assessmentAPI.getAssessmentRequest(latestRerunnable.id);
        if (!active) return;
        setSnapshot(normalizeFarmSnapshot(archive));
        setSnapshotSource(latestRerunnable);
      } catch (err) {
        if (active) {
          setSnapshot(null);
          setSnapshotSource(null);
          setSnapshotError(
            err instanceof Error ? err.message : 'Could not load crop details.'
          );
        }
      } finally {
        if (active) setSnapshotLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [loading, farm, assessments.length, latestRerunnable]);

  const locationLine = useMemo(() => {
    if (!farm) return '';
    return [farm.location, farm.region, farm.country].filter(Boolean).join(', ');
  }, [farm]);

  const sizeDiffers =
    farm?.size_ha != null &&
    snapshot?.assessedSizeHa != null &&
    Math.abs(farm.size_ha - snapshot.assessedSizeHa) > 0.001;

  const cropSummaryNode = (() => {
    if (!farm) return null;
    if (snapshotLoading) return <FarmCropSummary mode="loading" />;
    if (snapshotError) {
      return (
        <section className="rounded-2xl border border-red-200 bg-red-50 p-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-red-700">
            Crops &amp; land use
          </h3>
          <p className="mt-2 text-sm text-red-700">{snapshotError}</p>
        </section>
      );
    }
    if (assessments.length === 0) {
      return <FarmCropSummary mode="empty" emptyKind="none" farmId={farm.id} />;
    }
    if (!latestRerunnable) {
      return <FarmCropSummary mode="empty" emptyKind="legacy" farmId={farm.id} />;
    }
    if (snapshot && snapshotSource) {
      if (snapshot.crops.length === 0) {
        return <FarmCropSummary mode="empty" emptyKind="empty-crops" farmId={farm.id} />;
      }
      return (
        <FarmCropSummary
          mode="ready"
          snapshot={snapshot}
          assessmentId={snapshotSource.id}
          assessmentDate={snapshotSource.created_at}
          assessmentTitle={snapshotSource.title || snapshotSource.company_name}
        />
      );
    }
    return <FarmCropSummary mode="loading" />;
  })();

  const confirmDelete = async () => {
    if (!farm) return;
    setDeleting(true);
    try {
      await assessmentAPI.deleteFarm(farm.id);
      router.push('/dashboard/farms');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the farm.');
      setPendingDelete(false);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading farm profile…
      </div>
    );
  }

  if (error || !farm) {
    return (
      <div className="space-y-4">
        <Link href="/dashboard/farms" className="inline-flex items-center gap-1 text-sm font-medium text-moss hover:text-spruce">
          <ArrowLeft className="w-4 h-4" /> Back to farms
        </Link>
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error || 'Farm not found.'}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link href="/dashboard/farms" className="inline-flex items-center gap-1 text-sm font-medium text-moss hover:text-spruce">
            <ArrowLeft className="w-4 h-4" /> Back to farms
          </Link>
          <div className="mt-3 flex items-start gap-3">
            <div className="rounded-xl bg-moss/10 p-3 text-spruce">
              <Sprout className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-gray-900">{farm.name}</h2>
              <p className="text-sm text-gray-500">Farm profile</p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/assessment?farmId=${farm.id}`}
            className="inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2 text-sm font-medium text-white hover:bg-ink"
          >
            New assessment
          </Link>
          <Link
            href={`/dashboard/farms?edit=${farm.id}`}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Pencil className="w-4 h-4" /> Edit
          </Link>
          <button
            type="button"
            onClick={() => setPendingDelete(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            <Trash2 className="w-4 h-4" /> Delete
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="lg:col-span-2 rounded-2xl border border-gray-200 bg-white p-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Profile details</h3>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <ProfileField icon={MapPin} label="Place" value={locationLine || '—'} />
            <div>
              <dt className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-400">
                <Ruler className="w-3.5 h-3.5" />
                Farm size
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {farm.size_ha != null ? `${farm.size_ha} hectares` : '—'}
              </dd>
              {sizeDiffers && snapshot?.assessedSizeHa != null && (
                <p className="mt-1 text-xs text-gray-500">
                  Latest assessment: {snapshot.assessedSizeHa} hectares
                </p>
              )}
            </div>
            <ProfileField icon={User} label="Farmer / owner" value={farm.farmer_name || '—'} />
            <ProfileField icon={Phone} label="Contact" value={farm.farmer_contact || '—'} />
            <ProfileField
              icon={StickyNote}
              label="Notes"
              value={farm.notes || '—'}
              className="sm:col-span-2"
            />
          </dl>
          <p className="mt-6 text-xs text-gray-400">
            Added {farm.created_at ? new Date(farm.created_at).toLocaleDateString() : '—'}
          </p>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-6">
          <div className="flex items-center gap-2">
            <FileBarChart className="w-4 h-4 text-moss" />
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Assessments
            </h3>
          </div>
          <p className="mt-2 text-3xl font-bold text-gray-900">{assessments.length}</p>
          <p className="text-sm text-gray-500">linked to this farm</p>

          {assessments.length === 0 ? (
            <p className="mt-4 text-sm text-gray-500">No assessments yet.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {assessments.slice(0, 8).map((a) => (
                <li key={a.id}>
                  <Link
                    href={`/results?id=${a.id}`}
                    className="block rounded-lg border border-gray-100 px-3 py-2 hover:border-moss/40 hover:bg-moss/5"
                  >
                    <div className="text-sm font-medium text-gray-900">
                      {a.title || a.company_name || 'Untitled'}
                    </div>
                    <div className="text-xs text-gray-500">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                      {typeof a.single_score === 'number' ? ` · ${a.single_score.toFixed(3)}` : ''}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {assessments.length > 8 && (
            <Link
              href="/dashboard/assessments"
              className="mt-3 inline-block text-sm font-medium text-moss hover:text-spruce"
            >
              View all assessments
            </Link>
          )}
        </section>
      </div>

      {cropSummaryNode}

      <ConfirmDialog
        open={pendingDelete}
        title="Delete this farm?"
        description={
          <>
            This removes <strong>{farm.name}</strong> from your dashboard. Saved assessments are
            kept but unlinked from this farm.
          </>
        }
        confirmLabel="Delete farm"
        requireText={farm.name}
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(false)}
      />
    </div>
  );
}

function ProfileField({
  icon: Icon,
  label,
  value,
  className = '',
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-400">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </dt>
      <dd className="mt-1 text-sm text-gray-900 whitespace-pre-wrap">{value}</dd>
    </div>
  );
}

export default function FarmProfilePage() {
  return (
    <RequireAuth roles={['farmer']}>
      <DashboardShell active="farms" title="Farm profile">
        <FarmProfileContent />
      </DashboardShell>
    </RequireAuth>
  );
}
