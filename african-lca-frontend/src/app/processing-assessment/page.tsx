'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm, FormProvider } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Factory, Package, Zap, ClipboardCheck, CheckCircle, ChevronLeft, ChevronRight,
  AlertTriangle, Clock,
} from 'lucide-react';

import Layout from '@/components/Layout';
import RequireAuth from '@/components/RequireAuth';
import { assessmentAPI } from '@/lib/api';
import { COUNTRY_TO_REGION } from '@/lib/country-examples';
import {
  processingAssessmentSchema,
  buildProcessingPayload,
  defaultProcessingForm,
  ProcessingFormData,
  ProcessingStep,
  PROCESSING_FORM_STEPS,
  STEP_FIELDS,
  getProcessingStepProgress,
  getNextProcessingStep,
  getPreviousProcessingStep,
  COUNTRIES,
} from '@/lib/processing-assessment-schema';
import FacilityStep from '@/components/processing-assessment/FacilityStep';
import ProductsStep from '@/components/processing-assessment/ProductsStep';
import UtilitiesStep from '@/components/processing-assessment/UtilitiesStep';
import ReviewStep from '@/components/processing-assessment/ReviewStep';

export const dynamic = 'force-dynamic';

const STEP_ICONS: Record<ProcessingStep, React.ComponentType<{ className?: string }>> = {
  [ProcessingStep.FACILITY]: Factory,
  [ProcessingStep.PRODUCTS]: Package,
  [ProcessingStep.UTILITIES]: Zap,
  [ProcessingStep.REVIEW]: ClipboardCheck,
};

function ProcessingWizard() {
  const router = useRouter();
  const params = useSearchParams();
  const facilityId = params.get('facilityId');

  const [currentStep, setCurrentStep] = useState<ProcessingStep>(ProcessingStep.FACILITY);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // No explicit generic: let react-hook-form infer the input/transformed types from the
  // zod resolver. An explicit <ProcessingFormData> (the OUTPUT type) clashes with the
  // resolver's INPUT type because of .default()/.preprocess (optional-in, required-out).
  const methods = useForm({
    resolver: zodResolver(processingAssessmentSchema),
    defaultValues: defaultProcessingForm(),
    mode: 'onSubmit',
  });
  const { handleSubmit, trigger, setValue } = methods;

  // Prefill the facility section when launched from Facilities -> New assessment.
  useEffect(() => {
    if (!facilityId) return;
    let active = true;
    assessmentAPI
      .getFacilities()
      .then((list) => {
        const f = list.find((x) => x.id === facilityId);
        if (!active || !f) return;
        setValue('facility.facilityName', f.name);
        if (f.facility_type) setValue('facility.facilityType', f.facility_type as ProcessingFormData['facility']['facilityType']);
        if (f.country && (COUNTRIES as readonly string[]).includes(f.country)) {
          setValue('facility.country', f.country as ProcessingFormData['facility']['country']);
        }
        if (f.region) setValue('facility.region', f.region);
      })
      .catch(() => {});
    return () => { active = false; };
  }, [facilityId, setValue]);

  // Keep the new step in view — Next/Back leave the scroll at the previous footer otherwise.
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
  }, [currentStep]);

  const goNext = async () => {
    const valid = await trigger(STEP_FIELDS[currentStep]);
    if (!valid) return;
    const next = getNextProcessingStep(currentStep);
    if (next) setCurrentStep(next);
  };
  const goPrevious = () => {
    const prev = getPreviousProcessingStep(currentStep);
    if (prev) setCurrentStep(prev);
  };

  const onSubmit = async (data: ProcessingFormData) => {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const payload = buildProcessingPayload(data, COUNTRY_TO_REGION, { facilityId });
      const result = await assessmentAPI.submitProcessingAssessment(payload);
      localStorage.setItem(`assessment_${result.id}`, JSON.stringify(result));
      localStorage.setItem('lastAssessmentId', result.id);
      setDone(true);
      setTimeout(() => router.push(`/results?id=${result.id}&type=processing`), 1200);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Assessment failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const stepInfo = PROCESSING_FORM_STEPS.find((s) => s.id === currentStep);
  const stepIndex = PROCESSING_FORM_STEPS.findIndex((s) => s.id === currentStep);
  const progress = getProcessingStepProgress(currentStep);

  const renderStep = () => {
    switch (currentStep) {
      case ProcessingStep.FACILITY: return <FacilityStep />;
      case ProcessingStep.PRODUCTS: return <ProductsStep />;
      case ProcessingStep.UTILITIES: return <UtilitiesStep />;
      case ProcessingStep.REVIEW:
        return <ReviewStep onSubmit={handleSubmit(onSubmit)} isSubmitting={submitting} onPrevious={goPrevious} />;
    }
  };

  if (done) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto px-4 py-20 text-center">
          <div className="inline-grid place-items-center w-16 h-16 rounded-2xl bg-moss/10">
            <CheckCircle className="w-9 h-9 text-moss" />
          </div>
          <h1 className="mt-4 text-2xl font-bold text-ink">Assessment complete</h1>
          <p className="mt-2 text-muted">Taking you to the results…</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="min-h-screen bg-paper py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="text-center mb-10">
            <div className="inline-grid place-items-center w-14 h-14 rounded-2xl bg-moss/10 text-spruce mx-auto">
              <Factory className="w-7 h-7" />
            </div>
            <p className="eyebrow mt-4">Processing assessment · ISO 14040/14044</p>
            <h1 className="text-3xl md:text-4xl font-bold text-ink mt-2">Processing facility assessment</h1>
            <p className="mt-2 text-muted max-w-2xl mx-auto">
              Measure the environmental footprint of a processing site and its products, step by step.
            </p>
          </div>

          {/* Progress */}
          <div className="mb-8 bg-surface rounded-2xl p-5 border border-line">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 text-sm text-muted">
                <Clock className="w-4 h-4 text-moss" />
                <span>Estimated time: {stepInfo?.estimatedTime}</span>
              </div>
              <div className="text-sm font-semibold text-moss">Step {stepIndex + 1} / {PROCESSING_FORM_STEPS.length}</div>
            </div>
            <div className="relative w-full bg-line/60 rounded-full h-2 overflow-hidden">
              <motion.div
                className="absolute top-0 left-0 h-full bg-moss rounded-full"
                initial={false}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
            {/* Step markers */}
            <div className="mt-5 flex items-center justify-between">
              {PROCESSING_FORM_STEPS.map((step, index) => {
                const Icon = STEP_ICONS[step.id];
                const isActive = step.id === currentStep;
                const isDone = index < stepIndex;
                return (
                  <div key={step.id} className="flex flex-col items-center gap-1.5 flex-1">
                    <div
                      className={`w-10 h-10 rounded-xl grid place-items-center border-2 transition-colors ${
                        isActive ? 'bg-spruce border-moss text-white'
                          : isDone ? 'bg-moss/10 border-moss text-moss'
                            : 'bg-paper border-line text-muted'
                      }`}
                    >
                      {isDone ? <CheckCircle className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
                    </div>
                    <span className={`text-[11px] text-center ${isActive ? 'text-moss font-semibold' : 'text-muted'}`}>
                      {step.title}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Form card */}
          <div className="bg-surface rounded-2xl border border-line overflow-hidden">
            <div className="bg-spruce px-6 py-5">
              <h2 className="text-xl font-semibold text-white">{stepInfo?.title}</h2>
              <p className="text-paper/80 text-sm mt-1">{stepInfo?.description}</p>
            </div>

            <FormProvider {...methods}>
              <form onSubmit={(e) => e.preventDefault()} className="p-6" noValidate>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={currentStep}
                    initial={{ opacity: 0, x: 16 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -16 }}
                    transition={{ duration: 0.2 }}
                  >
                    {renderStep()}
                  </motion.div>
                </AnimatePresence>
              </form>
            </FormProvider>

            {/* Footer nav (Review step has its own buttons) */}
            {currentStep !== ProcessingStep.REVIEW && (
              <div className="bg-paper px-6 py-4 flex justify-between items-center border-t border-line">
                <button
                  type="button"
                  onClick={goPrevious}
                  disabled={currentStep === ProcessingStep.FACILITY}
                  className="flex items-center gap-2 px-6 py-2.5 border border-line rounded-full text-ink font-semibold hover:bg-surface disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="w-5 h-5" />
                  <span>Previous</span>
                </button>
                <button
                  type="button"
                  onClick={goNext}
                  className="flex items-center gap-2 bg-spruce text-white px-6 py-2.5 rounded-full font-semibold hover:bg-ink transition-colors"
                >
                  <span>Next step</span>
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>

          {submitError && (
            <div className="mt-6 flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 max-w-2xl mx-auto">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

export default function ProcessingAssessmentPage() {
  return (
    <RequireAuth roles={['processor', 'researcher']}>
      <Suspense fallback={null}>
        <ProcessingWizard />
      </Suspense>
    </RequireAuth>
  );
}
