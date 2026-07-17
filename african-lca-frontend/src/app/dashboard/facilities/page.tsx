'use client';

import React, { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Plus, Pencil, Trash2, Factory, MapPin, X, Eye } from 'lucide-react';
import RequireAuth from '@/components/RequireAuth';
import DashboardShell from '@/components/DashboardShell';
import { assessmentAPI, AssessmentSummary, Facility } from '@/lib/api';

export const dynamic = 'force-dynamic';

const COUNTRIES = ['Canada', 'Ghana', 'Nigeria'];
const FACILITY_TYPES = [
  'Mill', 'Bakery', 'CassivaProcessing', 'RiceProcessing', 'PalmOilMill', 'CocoaProcessing',
  'FishProcessing', 'MeatProcessing', 'DairyProcessing', 'FruitProcessing', 'VegetableProcessing', 'General',
];

type FacilityForm = {
  name: string;
  facility_type: string;
  country: string;
  region: string;
  location: string;
  notes: string;
};

const EMPTY: FacilityForm = { name: '', facility_type: 'General', country: 'Canada', region: '', location: '', notes: '' };

function FacilitiesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [assessments, setAssessments] = useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Facility | null>(null);
  const [form, setForm] = useState<FacilityForm>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [f, a] = await Promise.all([assessmentAPI.getFacilities(), assessmentAPI.getMyAssessments()]);
      setFacilities(f);
      setAssessments(a.assessments);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your facilities.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const countByFacility = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of assessments) if (a.facility_id) m.set(a.facility_id, (m.get(a.facility_id) || 0) + 1);
    return m;
  }, [assessments]);

  const openAdd = () => {
    setEditing(null);
    setForm(EMPTY);
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (facility: Facility) => {
    setEditing(facility);
    setForm({
      name: facility.name,
      facility_type: facility.facility_type || 'General',
      country: facility.country || 'Canada',
      region: facility.region || '',
      location: facility.location || '',
      notes: facility.notes || '',
    });
    setFormError(null);
    setModalOpen(true);
  };

  // Profile page "Edit" lands here with ?edit=<facilityId>
  useEffect(() => {
    const editId = searchParams.get('edit');
    if (!editId || facilities.length === 0) return;
    const facility = facilities.find((f) => f.id === editId);
    if (facility) {
      openEdit(facility);
      router.replace('/dashboard/facilities', { scroll: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- open once when list + query are ready
  }, [searchParams, facilities, router]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSaving(true);
    const payload = {
      name: form.name.trim(),
      facility_type: form.facility_type || undefined,
      country: form.country || undefined,
      region: form.region.trim() || undefined,
      location: form.location.trim() || undefined,
      notes: form.notes.trim() || undefined,
    };
    try {
      if (editing) await assessmentAPI.updateFacility(editing.id, payload);
      else await assessmentAPI.createFacility(payload);
      setModalOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not save the facility.');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (facility: Facility) => {
    if (!window.confirm(`Delete "${facility.name}"? Saved assessments are kept but unlinked from this facility.`)) return;
    try {
      await assessmentAPI.deleteFacility(facility.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the facility.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <p className="text-gray-600">
          Your facility profiles. Starting an assessment from a facility prefills its details.
        </p>
        <button
          type="button"
          onClick={openAdd}
          className="inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2.5 font-medium text-white hover:bg-ink transition-colors"
        >
          <Plus className="w-4 h-4" /> Add facility
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-gray-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : facilities.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-12 text-center">
          <Factory className="w-8 h-8 text-moss mx-auto" />
          <p className="mt-3 text-gray-600">No facilities yet. Add your first processing site.</p>
          <button
            type="button"
            onClick={openAdd}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2 font-medium text-white hover:bg-ink transition-colors"
          >
            <Plus className="w-4 h-4" /> Add facility
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {facilities.map((facility) => {
            const count = countByFacility.get(facility.id) || 0;
            return (
              <div key={facility.id} className="flex flex-col rounded-2xl border border-gray-200 bg-white p-5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <Link
                      href={`/dashboard/facilities/${facility.id}`}
                      className="font-semibold text-gray-900 hover:text-spruce"
                    >
                      {facility.name}
                    </Link>
                    <p className="mt-0.5 text-sm text-gray-500">{facility.facility_type}</p>
                    {(facility.location || facility.country) && (
                      <p className="mt-0.5 flex items-center gap-1 text-sm text-gray-500">
                        <MapPin className="w-3.5 h-3.5" />
                        {[facility.location, facility.region, facility.country].filter(Boolean).join(', ')}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Link
                      href={`/dashboard/facilities/${facility.id}`}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100"
                      aria-label="View facility profile"
                    >
                      <Eye className="w-4 h-4" />
                    </Link>
                    <button
                      type="button"
                      onClick={() => openEdit(facility)}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100"
                      aria-label="Edit facility"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(facility)}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50"
                      aria-label="Delete facility"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between gap-3 pt-4 border-t border-gray-100">
                  <span className="text-sm text-gray-500">
                    {count} {count === 1 ? 'assessment' : 'assessments'}
                  </span>
                  <div className="flex items-center gap-3">
                    <Link
                      href={`/dashboard/facilities/${facility.id}`}
                      className="text-sm font-medium text-gray-600 hover:text-spruce"
                    >
                      View profile
                    </Link>
                    <Link
                      href={`/processing-assessment?facilityId=${facility.id}`}
                      className="text-sm font-medium text-moss hover:text-spruce"
                    >
                      New assessment →
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/40" onClick={() => setModalOpen(false)} />
          <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
              <h3 className="text-lg font-semibold text-gray-900">{editing ? 'Edit facility' : 'Add facility'}</h3>
              <button type="button" onClick={() => setModalOpen(false)} className="p-1 text-gray-400 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={save} className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
              <Field label="Facility name" required>
                <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Facility type">
                  <select
                    value={form.facility_type}
                    onChange={(e) => setForm({ ...form, facility_type: e.target.value })}
                    className="input"
                  >
                    {FACILITY_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Country">
                  <select value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} className="input">
                    {COUNTRIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Region / province" hint="e.g. Ashanti, Western, Lagos">
                  <input value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} className="input" />
                </Field>
                <Field
                  label="Town / site address"
                  hint="More specific than region — town, industrial area, or street address of the facility"
                >
                  <input
                    value={form.location}
                    onChange={(e) => setForm({ ...form, location: e.target.value })}
                    className="input"
                    placeholder="e.g. Takoradi industrial area"
                  />
                </Field>
              </div>
              <Field label="Notes">
                <textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" />
              </Field>

              {formError && (
                <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">{formError}</div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="rounded-lg px-4 py-2 font-medium text-gray-600 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2 font-medium text-white hover:bg-ink disabled:opacity-60"
                >
                  {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                  {editing ? 'Save changes' : 'Add facility'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <style jsx>{`
        :global(.input) {
          margin-top: 0.25rem;
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid #d1d5db;
          padding: 0.5rem 0.75rem;
          color: #111827;
          outline: none;
        }
        :global(.input:focus) {
          border-color: #22c55e;
          box-shadow: 0 0 0 2px #bbf7d0;
        }
      `}</style>
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-gray-500">{hint}</span>}
    </label>
  );
}

export default function FacilitiesPage() {
  return (
    <RequireAuth roles={['processor']}>
      <DashboardShell active="facilities" title="Facilities">
        <Suspense fallback={<div className="text-gray-500 text-sm">Loading…</div>}>
          <FacilitiesContent />
        </Suspense>
      </DashboardShell>
    </RequireAuth>
  );
}
