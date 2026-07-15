'use client';

import React, { useState } from 'react';
import { FileCheck, ChevronDown, ShieldAlert, AlertTriangle, ClipboardList } from 'lucide-react';

/**
 * ISOReport — renders the deterministic, data-backed ISO 14040/14044 report block
 * (results.iso_report) produced by the engine, formatted ISO-conformant and review-ready
 * for external/public communication.
 *
 * Integrity: for a public/external report ISO 14044 §6.3 + ISO/TS 14071:2024 require an
 * independent critical review by a qualified panel BEFORE public disclosure. That review
 * is not done by the generator, so this renders a clearly-marked DRAFT with the critical
 * review shown as REQUIRED and PENDING — never as reviewed/approved.
 */

interface Category { name: string; unit: string }
interface RefFlow { process: string; amount: string; source: string; adaptation: string }
interface PanelMember { role: string; name: string; affiliation: string; status: string }

interface IsoReport {
  standard: string;
  disclosure_posture: string;
  conformance_status: string;
  document_control: {
    title: string; confidentiality: string; commissioner: string; practitioner: string;
    date_of_issue: string; report_number: string; version: string;
    reference_standards: string[]; farm_certifications: string[];
  };
  goal: {
    reasons_for_study: string; intended_application: string; intended_audience: string;
    commissioner: string; comparative_assertion_disclosed_to_public: boolean;
    public_disclosure_intended: boolean; peer_review_statement: string;
  };
  scope: {
    product_system: string; functional_unit: string; system_boundary: string;
    boundary_type: string; cutoff_criteria: string; allocation_procedure: string;
    lcia_method: string; perspective: string; impact_categories: Category[];
    normalization_reference: string; data_requirements: { foreground: string; background: string };
    assumptions_and_limitations: string[]; value_choices: string[];
  };
  inventory_analysis: {
    data_sources: string[]; foreground_data: string; background_data: string; on_farm_lci: string;
    calculation_procedure: string; reference_flows: RefFlow[]; inputs_matched: string;
    pedigree_uncertainty: string; data_validation: string; notes: string[]; unlinked_flows?: string[];
  };
  impact_assessment: {
    method: string; rationale: string; mandatory_elements: Record<string, string>;
    optional_elements: Record<string, string>; results_are_relative_expressions: string;
    n_categories_reported: number;
  };
  interpretation: {
    significant_issues: string[]; data_quality_assessment: string; completeness_check: string;
    consistency_check: string; sensitivity_and_uncertainty: string; conclusions: string[];
    recommendations: string[]; limitations: string[]; public_disclosure: string;
  };
  critical_review: {
    required: boolean; status: string; trigger: string; reviewer_requirements: string[];
    review_scope: string[]; process: string[]; panel: PanelMember[]; statement: string;
  };
  references: string[];
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="text-[13px] font-bold text-gray-900 mb-1">{label}</div>
      <div className="text-sm text-gray-700 leading-relaxed">{children}</div>
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="text-sm text-gray-800 space-y-1 list-disc pl-5 leading-relaxed">
      {items.map((it, i) => <li key={i}>{it}</li>)}
    </ul>
  );
}

function Phase({ num, title, clause, defaultOpen = false, children }:
  { num: string; title: string; clause: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
      <button type="button" onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors">
        <span className="flex items-center gap-3 text-left">
          <span className="flex-shrink-0 w-8 h-8 rounded-lg bg-emerald-600 text-white text-sm font-bold flex items-center justify-center">{num}</span>
          <span>
            <span className="block font-bold text-gray-900">{title}</span>
            <span className="block text-xs text-gray-500">{clause}</span>
          </span>
        </span>{/* clause = plain-language descriptor, no standards codes */}
        <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div className="px-5 pb-5 pt-1 border-t border-gray-100">{children}</div>}
    </div>
  );
}

export default function ISOReport({ report }: { report?: IsoReport }) {
  // Guard against a stale/old-shape payload (e.g. an assessment generated before the
  // ISO-conformant report was added): render nothing rather than crash the results page.
  if (!report || !report.document_control || !report.critical_review || !report.goal) return null;
  const { document_control: dc, goal, scope, inventory_analysis: lci,
    impact_assessment: lcia, interpretation, critical_review: cr } = report;
  const pending = cr.required && !cr.statement;

  return (
    <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50/60 to-white p-6 md:p-8">
      <div className="flex items-center gap-3 mb-1">
        <FileCheck className="w-7 h-7 text-emerald-600" />
        <h3 className="text-2xl font-bold text-gray-900">ISO 14044 Report</h3>
      </div>
      <p className="text-sm text-gray-600 mb-5">
        Based on {report.standard}. {report.disclosure_posture}. Every part is built from this assessment.
      </p>

      {/* Draft / pending-review banner: the integrity gate */}
      {pending && (
        <div className="mb-6 rounded-xl border-2 border-amber-300 bg-amber-50 p-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-amber-900">Draft report. It needs an independent critical review before it can be shared publicly.</div>
              <p className="text-sm text-amber-800 mt-1 leading-relaxed">{report.conformance_status}</p>
            </div>
          </div>
        </div>
      )}

      {/* Document control */}
      <div className="mb-6 rounded-xl border border-gray-200 bg-white p-5">
        <div className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-3 flex items-center gap-1.5">
          <ClipboardList className="w-4 h-4" /> Document control
        </div>
        <div className="text-base font-bold text-gray-900 mb-3">{dc.title}</div>
        <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {[['Commissioner', dc.commissioner], ['Practitioner', dc.practitioner],
            ['Date of issue', dc.date_of_issue], ['Report no.', dc.report_number],
            ['Version', dc.version], ['Confidentiality', dc.confidentiality],
            ['Reference standards', dc.reference_standards.join(', ')],
            ['Certifications', dc.farm_certifications.length ? dc.farm_certifications.join(', ') : 'None recorded']]
            .map(([k, v]) => (
              <div key={k as string}>
                <span className="font-bold text-gray-900">{k}: </span>
                <span className="text-gray-700">{v}</span>
              </div>
            ))}
        </div>
      </div>

      <div className="space-y-3">
        {/* 1. Goal */}
        <Phase num="1" title="Goal" clause="What the study is for and who it is for" defaultOpen>
          <Field label="Reasons for the study">{goal.reasons_for_study}</Field>
          <Field label="Intended application">{goal.intended_application}</Field>
          <Field label="Intended audience">{goal.intended_audience}</Field>
          <Field label="Commissioner">{goal.commissioner}</Field>
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
            <div className="text-[13px] font-bold text-blue-900 mb-1">Peer and critical review</div>
            <div className="text-sm text-gray-700 leading-relaxed">{goal.peer_review_statement}</div>
          </div>
        </Phase>

        {/* 2. Scope */}
        <Phase num="2" title="Scope" clause="What was assessed, and how" defaultOpen>
          <div className="mb-4 rounded-lg bg-emerald-600 text-white px-4 py-3">
            <div className="text-xs font-bold uppercase tracking-wide opacity-90">Functional unit</div>
            <div className="text-lg font-bold">{scope.functional_unit}</div>
          </div>
          <Field label="Product system">{scope.product_system}</Field>
          <Field label="System boundary">{scope.system_boundary}</Field>
          <div className="grid md:grid-cols-2 gap-x-6">
            <Field label="Boundary type">{scope.boundary_type}</Field>
            <Field label="LCIA method">{scope.lcia_method} · {scope.perspective}</Field>
          </div>
          <Field label="Cut-off criteria">{scope.cutoff_criteria}</Field>
          <Field label="Allocation procedure">{scope.allocation_procedure}</Field>
          <Field label={`Impact categories (${scope.impact_categories.length})`}>
            <div className="flex flex-wrap gap-1.5">
              {scope.impact_categories.map((c, i) => (
                <span key={i} className="text-xs bg-white border border-gray-200 rounded-full px-2.5 py-1">
                  {c.name} <span className="text-gray-400">({c.unit})</span>
                </span>
              ))}
            </div>
          </Field>
          <div className="grid md:grid-cols-2 gap-x-6">
            <Field label="Foreground data">{scope.data_requirements.foreground}</Field>
            <Field label="Background data">{scope.data_requirements.background}</Field>
          </div>
          <Field label="Assumptions & limitations"><Bullets items={scope.assumptions_and_limitations} /></Field>
          <div className="mt-3 rounded-lg bg-amber-50 border border-amber-200 p-3">
            <div className="text-[13px] font-bold text-amber-900 mb-1 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" /> Judgement calls
            </div>
            <Bullets items={scope.value_choices} />
          </div>
        </Phase>

        {/* 3. Inventory */}
        <Phase num="3" title="Life Cycle Inventory" clause="The data behind the results">
          <Field label="Data sources"><Bullets items={lci.data_sources} /></Field>
          <div className="grid md:grid-cols-2 gap-x-6">
            <Field label="Foreground data">{lci.foreground_data}</Field>
            <Field label="Background data">{lci.background_data}</Field>
          </div>
          <Field label="On-farm inventory">{lci.on_farm_lci}</Field>
          <Field label="Calculation procedure">{lci.calculation_procedure}</Field>
          <Field label="Reference flows linked to the functional unit">
            <div className="overflow-x-auto">
              <table className="w-full text-xs border border-gray-200 rounded-lg overflow-hidden">
                <thead className="bg-gray-50">
                  <tr>
                    {['Process / Material', 'Amount', 'Source', 'Adaptation'].map(h => (
                      <th key={h} className="text-left font-semibold text-gray-600 px-3 py-2 border-b border-gray-200">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {lci.reference_flows.map((r, i) => (
                    <tr key={i} className="odd:bg-white even:bg-gray-50/50">
                      <td className="px-3 py-2 border-b border-gray-100">{r.process}</td>
                      <td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap">{r.amount}</td>
                      <td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap">{r.source}</td>
                      <td className="px-3 py-2 border-b border-gray-100">{r.adaptation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Field>
          <Field label="Inputs matched">{lci.inputs_matched}</Field>
          <Field label="Data pedigree & uncertainty">{lci.pedigree_uncertainty}</Field>
          <Field label="Data validation">{lci.data_validation}</Field>
          {lci.unlinked_flows && lci.unlinked_flows.length > 0 && (
            <Field label="Unlinked / unmatched"><Bullets items={lci.unlinked_flows} /></Field>
          )}
          {lci.notes && lci.notes.length > 0 && <Field label="Notes"><Bullets items={lci.notes} /></Field>}
        </Phase>

        {/* 4. Impact assessment */}
        <Phase num="4" title="Life Cycle Impact Assessment" clause="How the impacts were worked out">
          <Field label="Method and why it was chosen">{lcia.method}. {lcia.rationale}</Field>
          <Field label="Required steps">
            <Bullets items={Object.values(lcia.mandatory_elements)} />
          </Field>
          <Field label="Optional steps">
            <Bullets items={Object.values(lcia.optional_elements)} />
          </Field>
          <div className="mt-3 rounded-lg bg-red-50 border border-red-200 p-3">
            <div className="text-[13px] font-bold text-red-800 mb-1">Important note on how to read these results</div>
            <div className="text-sm text-gray-700 leading-relaxed">{lcia.results_are_relative_expressions}</div>
          </div>
        </Phase>

        {/* 5. Interpretation */}
        <Phase num="5" title="Interpretation" clause="What the results mean" defaultOpen>
          <Field label="What stands out"><Bullets items={interpretation.significant_issues} /></Field>
          <Field label="How good is the data">{interpretation.data_quality_assessment}</Field>
          <Field label="Is anything missing">{interpretation.completeness_check}</Field>
          <Field label="Is it internally consistent">{interpretation.consistency_check}</Field>
          <Field label="How sensitive are the results">{interpretation.sensitivity_and_uncertainty}</Field>
          <Field label="Conclusions"><Bullets items={interpretation.conclusions} /></Field>
          <Field label="Recommendations"><Bullets items={interpretation.recommendations} /></Field>
          <Field label="Limitations"><Bullets items={interpretation.limitations} /></Field>
          <div className="mt-3 rounded-lg bg-blue-50 border border-blue-200 p-3">
            <div className="text-[13px] font-bold text-blue-900 mb-1">Sharing this publicly</div>
            <div className="text-sm text-gray-700 leading-relaxed">{interpretation.public_disclosure}</div>
          </div>
        </Phase>

        {/* Critical review */}
        <div className={`rounded-xl border-2 p-5 ${pending ? 'border-amber-300 bg-amber-50/60' : 'border-purple-200 bg-purple-50/50'}`}>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <ShieldAlert className={`w-5 h-5 ${pending ? 'text-amber-600' : 'text-purple-600'}`} />
            <span className="font-bold text-gray-900">Independent critical review</span>
            <span className={`ml-auto text-xs font-bold px-2.5 py-1 rounded-full ${cr.required ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-700'}`}>
              {cr.status}
            </span>
          </div>
          {cr.trigger && <p className="text-sm text-gray-700 mb-3"><span className="font-bold text-gray-900">Why it is needed: </span>{cr.trigger}</p>}
          {cr.reviewer_requirements.length > 0 && (
            <Field label="Who should review it"><Bullets items={cr.reviewer_requirements} /></Field>
          )}
          {cr.review_scope.length > 0 && (
            <Field label="What gets reviewed">
              <div className="flex flex-wrap gap-1.5">
                {cr.review_scope.map((s, i) => (
                  <span key={i} className="text-xs bg-white border border-gray-200 rounded-full px-2.5 py-1">{s}</span>
                ))}
              </div>
            </Field>
          )}
          {cr.process.length > 0 && <Field label="How the review works"><Bullets items={cr.process} /></Field>}
          {cr.panel.length > 0 && (
            <Field label="The review panel">
              <div className="space-y-1">
                {cr.panel.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="font-bold text-gray-800 w-20">{p.role}</span>
                    <span className="text-gray-500">{p.name || 'to be appointed'}</span>
                    <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{p.status}</span>
                  </div>
                ))}
              </div>
            </Field>
          )}
          {cr.statement
            ? <Field label="Review statement">{cr.statement}</Field>
            : <p className="text-sm italic text-gray-600 mt-2">No review statement has been issued yet. It is added only once an independent panel has looked at the study and accepted it.</p>}
        </div>

        {/* References */}
        <Phase num="R" title="References" clause="Standards and data sources">
          <Bullets items={report.references} />
        </Phase>
      </div>
    </div>
  );
}
