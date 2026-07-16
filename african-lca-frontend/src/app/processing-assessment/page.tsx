'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Factory, Plus, Trash2, Loader2, CheckCircle, AlertTriangle } from 'lucide-react';
import Layout from '@/components/Layout';
import RequireAuth from '@/components/RequireAuth';
import { assessmentAPI } from '@/lib/api';
import { COUNTRY_TO_REGION } from '@/lib/country-examples';

export const dynamic = 'force-dynamic';

const COUNTRIES = ['Canada', 'Ghana', 'Nigeria'];
const FACILITY_TYPES = [
  'Mill', 'Bakery', 'CassivaProcessing', 'RiceProcessing', 'PalmOilMill', 'CocoaProcessing',
  'FishProcessing', 'MeatProcessing', 'DairyProcessing', 'FruitProcessing', 'VegetableProcessing', 'General',
];
const LOCATION_TYPES = ['Urban', 'PeriUrban', 'Rural', 'Industrial'];
const PRODUCT_TYPES = [
  'FlourMaize', 'FlourWheat', 'FlourCassava', 'FlourPlantain', 'RiceProcessed', 'PalmOil',
  'CocoaPowder', 'CocoaButter', 'BakedGoods', 'ProcessedFish', 'ProcessedMeat', 'Dairy',
  'FruitJuice', 'DriedFruits', 'Other',
];

interface ProductRow {
  name: string;
  product_type: string;
  annual_production: string; // tonnes
}

function ProcessingForm() {
  const router = useRouter();
  const params = useSearchParams();
  const facilityId = params.get('facilityId');

  const [facilityName, setFacilityName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [facilityType, setFacilityType] = useState('General');
  const [country, setCountry] = useState('Canada');
  const [region, setRegion] = useState('');
  const [locationType, setLocationType] = useState('Industrial');
  const [capacity, setCapacity] = useState('10'); // tonnes/day
  const [hoursPerDay, setHoursPerDay] = useState('8');
  const [daysPerYear, setDaysPerYear] = useState('250');
  const [products, setProducts] = useState<ProductRow[]>([
    { name: '', product_type: 'FlourWheat', annual_production: '' },
  ]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Prefill from the facility when launched from Facilities → New assessment.
  useEffect(() => {
    if (!facilityId) return;
    let active = true;
    assessmentAPI
      .getFacilities()
      .then((list) => {
        const f = list.find((x) => x.id === facilityId);
        if (!active || !f) return;
        setFacilityName(f.name);
        if (f.facility_type) setFacilityType(f.facility_type);
        if (f.country && COUNTRIES.includes(f.country)) setCountry(f.country);
        if (f.region) setRegion(f.region);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [facilityId]);

  const updateProduct = (i: number, patch: Partial<ProductRow>) =>
    setProducts((rows) => rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addProduct = () =>
    setProducts((rows) => [...rows, { name: '', product_type: 'FlourWheat', annual_production: '' }]);
  const removeProduct = (i: number) => setProducts((rows) => rows.filter((_, idx) => idx !== i));

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const validProducts = products.filter((p) => p.name.trim() && Number(p.annual_production) > 0);
    if (validProducts.length === 0) {
      setError('Add at least one product with a name and an annual production above zero.');
      return;
    }
    if (Number(capacity) <= 0) {
      setError('Processing capacity must be greater than zero.');
      return;
    }

    // UI country -> backend country + engine region (Canada => Global + CA).
    const mapped = COUNTRY_TO_REGION[country] ?? { country, region: region || undefined };

    const payload = {
      country: mapped.country,
      region: region || mapped.region,
      facility_id: facilityId ?? undefined,
      title: facilityName || companyName || undefined,
      facility_profile: {
        facility_name: facilityName.trim() || 'Facility',
        company_name: companyName.trim() || facilityName.trim() || 'Company',
        facility_type: facilityType,
        processing_capacity: Number(capacity),
        operational_hours_per_day: Number(hoursPerDay) || 8,
        operational_days_per_year: Number(daysPerYear) || 250,
        location_type: locationType,
      },
      processed_products: validProducts.map((p, i) => ({
        id: `product_${i + 1}`,
        name: p.name.trim(),
        product_type: p.product_type,
        annual_production: Number(p.annual_production),
      })),
    };

    setSubmitting(true);
    try {
      const result = await assessmentAPI.submitProcessingAssessment(payload);
      localStorage.setItem(`assessment_${result.id}`, JSON.stringify(result));
      localStorage.setItem('lastAssessmentId', result.id);
      setDone(true);
      setTimeout(() => router.push(`/results?id=${result.id}`), 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="text-center">
          <div className="inline-grid place-items-center w-14 h-14 rounded-2xl bg-moss/10 text-spruce">
            <Factory className="w-7 h-7" />
          </div>
          <h1 className="mt-4 text-3xl font-bold text-gray-900">Processing facility assessment</h1>
          <p className="mt-2 text-gray-600">
            Measure the environmental footprint of a processing site and its products.
          </p>
        </div>

        {done ? (
          <div className="mt-8 rounded-2xl border border-moss/30 bg-moss/10 px-6 py-8 text-center">
            <CheckCircle className="w-8 h-8 text-moss mx-auto" />
            <p className="mt-3 font-medium text-spruce">Assessment complete. Taking you to the results…</p>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-8 space-y-8">
            {/* Facility */}
            <section className="rounded-2xl border border-gray-200 bg-white p-6">
              <h2 className="text-lg font-semibold text-gray-900">Facility</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <Field label="Facility name" required>
                  <input required value={facilityName} onChange={(e) => setFacilityName(e.target.value)} className="input" />
                </Field>
                <Field label="Company name">
                  <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} className="input" />
                </Field>
                <Field label="Facility type">
                  <select value={facilityType} onChange={(e) => setFacilityType(e.target.value)} className="input">
                    {FACILITY_TYPES.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Location type">
                  <select value={locationType} onChange={(e) => setLocationType(e.target.value)} className="input">
                    {LOCATION_TYPES.map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Country">
                  <select value={country} onChange={(e) => setCountry(e.target.value)} className="input">
                    {COUNTRIES.map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Region / province">
                  <input value={region} onChange={(e) => setRegion(e.target.value)} className="input" />
                </Field>
                <Field label="Processing capacity (tonnes/day)" required>
                  <input type="number" min="0" step="any" required value={capacity} onChange={(e) => setCapacity(e.target.value)} className="input" />
                </Field>
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Hours / day">
                    <input type="number" min="0" step="any" value={hoursPerDay} onChange={(e) => setHoursPerDay(e.target.value)} className="input" />
                  </Field>
                  <Field label="Days / year">
                    <input type="number" min="0" step="1" value={daysPerYear} onChange={(e) => setDaysPerYear(e.target.value)} className="input" />
                  </Field>
                </div>
              </div>
            </section>

            {/* Products */}
            <section className="rounded-2xl border border-gray-200 bg-white p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Products</h2>
                <button type="button" onClick={addProduct} className="inline-flex items-center gap-1 text-sm font-medium text-moss hover:text-spruce">
                  <Plus className="w-4 h-4" /> Add product
                </button>
              </div>
              <div className="mt-4 space-y-4">
                {products.map((p, i) => (
                  <div key={i} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] items-end rounded-xl border border-gray-100 bg-gray-50 p-3">
                    <Field label="Product name">
                      <input value={p.name} onChange={(e) => updateProduct(i, { name: e.target.value })} className="input" />
                    </Field>
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Type">
                        <select value={p.product_type} onChange={(e) => updateProduct(i, { product_type: e.target.value })} className="input">
                          {PRODUCT_TYPES.map((t) => (
                            <option key={t}>{t}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Annual (tonnes)">
                        <input type="number" min="0" step="any" value={p.annual_production} onChange={(e) => updateProduct(i, { annual_production: e.target.value })} className="input" />
                      </Field>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeProduct(i)}
                      disabled={products.length === 1}
                      className="p-2 mb-1 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 disabled:opacity-40 disabled:hover:bg-transparent"
                      aria-label="Remove product"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </section>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-lg bg-spruce px-6 py-3 font-semibold text-white hover:bg-ink disabled:opacity-60 transition-colors"
              >
                {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                {submitting ? 'Running assessment…' : 'Run assessment'}
              </button>
            </div>
          </form>
        )}
      </div>

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
    </Layout>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </span>
      {children}
    </label>
  );
}

export default function ProcessingAssessmentPage() {
  return (
    <RequireAuth roles={['processor']}>
      <Suspense fallback={null}>
        <ProcessingForm />
      </Suspense>
    </RequireAuth>
  );
}
