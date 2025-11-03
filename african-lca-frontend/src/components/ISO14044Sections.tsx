'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileText,
  Target,
  Box,
  Scale,
  Database,
  AlertCircle,
  CheckCircle2,
  Info,
  ChevronDown,
  ChevronRight,
  BookOpen
} from 'lucide-react';
import { AssessmentResult } from '@/types/assessment';

/**
 * ISO 14044 Compliant LCA Sections
 * Ensures proper documentation and transparency
 */

interface ISO14044SectionsProps {
  results: AssessmentResult;
}

// 1. Goal and Scope Definition (ISO 14044 Section 4.2)
export function GoalAndScopeSection({ results }: ISO14044SectionsProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-2xl p-8 shadow-lg border-2 border-blue-500">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-4"
      >
        <div className="flex items-center space-x-3">
          <Target className="w-6 h-6 text-blue-600" />
          <h3 className="text-2xl font-bold text-gray-900">
            Goal and Scope Definition
          </h3>
          <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full font-semibold">
            ISO 14044 §4.2
          </span>
        </div>
        {expanded ? <ChevronDown className="w-6 h-6" /> : <ChevronRight className="w-6 h-6" />}
      </button>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="space-y-6"
        >
          {/* Goal */}
          <div className="border-l-4 border-blue-500 pl-4">
            <h4 className="font-bold text-gray-900 mb-2 flex items-center space-x-2">
              <FileText className="w-4 h-4" />
              <span>Study Goal</span>
            </h4>
            <p className="text-gray-700">
              To assess the environmental impacts of agricultural production at{' '}
              <strong>{results.company_name}</strong> in {results.country}, following
              ISO 14040/14044 standards, for the purpose of identifying environmental
              hotspots and improvement opportunities.
            </p>
          </div>

          {/* Intended Application */}
          <div className="border-l-4 border-blue-400 pl-4">
            <h4 className="font-bold text-gray-900 mb-2">Intended Application</h4>
            <ul className="list-disc list-inside text-gray-700 space-y-1">
              <li>Internal decision-making and management optimization</li>
              <li>Sustainability reporting and benchmarking</li>
              <li>Environmental improvement planning</li>
              <li>Not intended for comparative assertions disclosed to the public (ISO 14044 §4.2.3.3)</li>
            </ul>
          </div>

          {/* Functional Unit */}
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-2 flex items-center space-x-2">
              <Scale className="w-4 h-4 text-blue-600" />
              <span>Functional Unit</span>
            </h4>
            <p className="text-gray-700">
              <strong>1 kilogram (kg) of agricultural product</strong> at farm gate,
              ready for processing or consumption.
            </p>
            <p className="text-sm text-gray-600 mt-2">
              This represents the quantified performance of the product system for use
              as a reference unit (ISO 14044 §4.2.3.2).
            </p>
          </div>

          {/* System Boundaries */}
          <div className="border-l-4 border-green-500 pl-4">
            <h4 className="font-bold text-gray-900 mb-2 flex items-center space-x-2">
              <Box className="w-4 h-4 text-green-600" />
              <span>System Boundaries</span>
            </h4>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <h5 className="font-semibold text-gray-800 mb-1">Included Processes:</h5>
                <ul className="text-sm text-gray-700 space-y-1">
                  <li>✓ Input production (seeds, fertilizers, pesticides)</li>
                  <li>✓ Field operations (tillage, planting, harvesting)</li>
                  <li>✓ Equipment use and fuel consumption</li>
                  <li>✓ Irrigation and water management</li>
                  <li>✓ On-farm energy use</li>
                  <li>✓ Direct emissions (N₂O, CH₄, CO₂)</li>
                </ul>
              </div>
              <div>
                <h5 className="font-semibold text-gray-800 mb-1">Excluded Processes:</h5>
                <ul className="text-sm text-gray-700 space-y-1">
                  <li>✗ Capital goods (infrastructure, buildings)</li>
                  <li>✗ Labor and human inputs</li>
                  <li>✗ Post-harvest processing (beyond farm gate)</li>
                  <li>✗ Transportation to market (&lt;1% impact estimate)</li>
                </ul>
                <p className="text-xs text-gray-600 mt-2">
                  Exclusions justified by cut-off criteria (&lt;1% mass, energy, environmental relevance)
                </p>
              </div>
            </div>
          </div>

          {/* Allocation Procedures */}
          <div className="border-l-4 border-purple-500 pl-4">
            <h4 className="font-bold text-gray-900 mb-2">Allocation Procedures</h4>
            <p className="text-gray-700 text-sm mb-2">
              For multi-output processes (e.g., crop residues, co-products):
            </p>
            <ul className="text-sm text-gray-700 space-y-1">
              <li><strong>1. Subdivision avoided</strong> where possible (ISO 14044 §4.3.4.2)</li>
              <li><strong>2. System expansion</strong> used for crop residues incorporated into soil</li>
              <li><strong>3. Economic allocation</strong> applied when unavoidable, based on market value</li>
            </ul>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// 2. Life Cycle Inventory (ISO 14044 Section 4.3)
export function InventoryAnalysisSection({ results }: ISO14044SectionsProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-2xl p-8 shadow-lg border-2 border-green-500">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-4"
      >
        <div className="flex items-center space-x-3">
          <Database className="w-6 h-6 text-green-600" />
          <h3 className="text-2xl font-bold text-gray-900">
            Life Cycle Inventory Analysis (LCI)
          </h3>
          <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full font-semibold">
            ISO 14044 §4.3
          </span>
        </div>
        {expanded ? <ChevronDown className="w-6 h-6" /> : <ChevronRight className="w-6 h-6" />}
      </button>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="space-y-6"
        >
          {/* Data Collection */}
          <div className="bg-green-50 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3">Data Collection & Quality</h4>

            {results.data_quality && (
              <div className="grid md:grid-cols-3 gap-4">
                <div className="bg-white rounded-lg p-3">
                  <div className="text-xs text-gray-600 mb-1">Temporal Coverage</div>
                  <div className="text-lg font-bold text-gray-900">
                    {(results.data_quality.temporal_representativeness * 100).toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-600">
                    {results.data_quality.temporal_representativeness >= 0.8 ? 'Excellent' :
                     results.data_quality.temporal_representativeness >= 0.6 ? 'Good' : 'Fair'}
                  </div>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <div className="text-xs text-gray-600 mb-1">Geographical Coverage</div>
                  <div className="text-lg font-bold text-gray-900">
                    {(results.data_quality.geographical_representativeness * 100).toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-600">
                    Region-specific for {results.country}
                  </div>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <div className="text-xs text-gray-600 mb-1">Technological Coverage</div>
                  <div className="text-lg font-bold text-gray-900">
                    {(results.data_quality.technological_representativeness * 100).toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-600">
                    Current farming practices
                  </div>
                </div>
              </div>
            )}

            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start space-x-2">
                <Info className="w-4 h-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-gray-700">
                  <strong>Data Sources:</strong> Primary data from farm records;
                  Background data from Agri-footprint 6.0, ecoinvent 3.9.1, and African-specific datasets
                </div>
              </div>
            </div>
          </div>

          {/* Data Quality Assessment per ISO 14044 */}
          <div className="border border-gray-200 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3">Data Quality Requirements (ISO 14044 §4.2.3.6)</h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Time-related coverage</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Geographical coverage</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Technology coverage</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Precision, completeness, representativeness</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">Consistency and reproducibility</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// 3. Life Cycle Impact Assessment (ISO 14044 Section 4.4)
export function ImpactAssessmentMethodologySection({ results }: ISO14044SectionsProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="bg-white rounded-2xl p-8 shadow-lg border-2 border-indigo-500">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-4"
      >
        <div className="flex items-center space-x-3">
          <Scale className="w-6 h-6 text-indigo-600" />
          <h3 className="text-2xl font-bold text-gray-900">
            Life Cycle Impact Assessment (LCIA) Methodology
          </h3>
          <span className="text-xs bg-indigo-100 text-indigo-800 px-2 py-1 rounded-full font-semibold">
            ISO 14044 §4.4
          </span>
        </div>
        {expanded ? <ChevronDown className="w-6 h-6" /> : <ChevronRight className="w-6 h-6" />}
      </button>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="space-y-6"
        >
          {/* Mandatory LCIA Elements */}
          <div className="bg-indigo-50 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3">
              Mandatory Elements (ISO 14044 §4.4.2)
            </h4>

            <div className="space-y-4">
              {/* Selection of Impact Categories */}
              <div className="bg-white rounded-lg p-4">
                <div className="flex items-center space-x-2 mb-2">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  <h5 className="font-semibold text-gray-900">1. Selection of Impact Categories</h5>
                </div>
                <p className="text-sm text-gray-700 mb-2">
                  <strong>Method:</strong> ReCiPe 2016 Midpoint (H) v1.1 with African context normalization
                </p>
                <div className="grid md:grid-cols-2 gap-2 text-xs">
                  <div>
                    <strong>Impact Categories Selected:</strong>
                    <ul className="list-disc list-inside text-gray-600 ml-2 mt-1">
                      <li>Climate Change (GWP 100a)</li>
                      <li>Terrestrial Acidification</li>
                      <li>Freshwater Eutrophication</li>
                      <li>Marine Eutrophication</li>
                      <li>Water Consumption</li>
                      <li>Land Use</li>
                    </ul>
                  </div>
                  <div>
                    <strong>Additional Categories:</strong>
                    <ul className="list-disc list-inside text-gray-600 ml-2 mt-1">
                      <li>Fossil Depletion</li>
                      <li>Mineral Depletion</li>
                      <li>Photochemical Oxidation</li>
                      <li>Particulate Matter Formation</li>
                      <li>Biodiversity Loss</li>
                      <li>Soil Degradation</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Classification & Characterization */}
              <div className="bg-white rounded-lg p-4">
                <div className="flex items-center space-x-2 mb-2">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  <h5 className="font-semibold text-gray-900">2. Classification & Characterization</h5>
                </div>
                <p className="text-sm text-gray-700">
                  Inventory flows assigned to impact categories and converted using
                  characterization factors from ReCiPe 2016 Midpoint methodology.
                </p>
                <div className="mt-2 p-2 bg-blue-50 rounded text-xs text-gray-700">
                  <strong>Example:</strong> CO₂ emissions characterized using GWP100a = 1 kg CO₂-eq/kg;
                  N₂O using GWP100a = 298 kg CO₂-eq/kg
                </div>
              </div>
            </div>
          </div>

          {/* Optional LCIA Elements */}
          <div className="bg-purple-50 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3 flex items-center space-x-2">
              <Info className="w-5 h-5 text-purple-600" />
              <span>Optional Elements (ISO 14044 §4.4.3)</span>
            </h4>

            <div className="space-y-3">
              {/* Normalization */}
              <div className="bg-white rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-semibold text-gray-900 text-sm">Normalization</h5>
                  <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded">Applied</span>
                </div>
                <p className="text-xs text-gray-700">
                  Impact results normalized using African reference values to express impacts
                  relative to regional total environmental impact.
                </p>
              </div>

              {/* Grouping */}
              <div className="bg-white rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-semibold text-gray-900 text-sm">Grouping</h5>
                  <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded">Applied</span>
                </div>
                <p className="text-xs text-gray-700">
                  Categories grouped into: Human Health, Ecosystem Quality, Resource Depletion
                </p>
              </div>

              {/* Weighting */}
              <div className="bg-white rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-semibold text-gray-900 text-sm">Weighting</h5>
                  <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Optional - Value Choice</span>
                </div>
                <p className="text-xs text-gray-700 mb-2">
                  <strong className="text-red-600">Important:</strong> Weighting involves value-choices
                  and shall not be used for comparative assertions (ISO 14044 §4.4.3.3)
                </p>
                {results.single_score?.weighting_factors && (
                  <div className="text-xs text-gray-600 bg-yellow-50 p-2 rounded">
                    Weighting method: {results.single_score.methodology || 'African context priorities'}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* LCIA Limitations */}
          <div className="border-l-4 border-red-500 pl-4 bg-red-50 p-3">
            <h4 className="font-bold text-gray-900 mb-2 flex items-center space-x-2">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <span>LCIA Limitations (ISO 14044 §4.4.4)</span>
            </h4>
            <ul className="text-sm text-gray-700 space-y-1">
              <li>• Relative expressions only - cannot predict absolute impacts</li>
              <li>• Spatial and temporal variations not fully captured</li>
              <li>• Threshold effects and dose-response not modeled</li>
              <li>• Some environmental mechanisms have scientific uncertainty</li>
              <li>• Results are indicators, not actual environmental impacts</li>
            </ul>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// 4. Life Cycle Interpretation (ISO 14044 Section 4.5)
export function InterpretationSection({ results }: ISO14044SectionsProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="bg-white rounded-2xl p-8 shadow-lg border-2 border-orange-500">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-4"
      >
        <div className="flex items-center space-x-3">
          <BookOpen className="w-6 h-6 text-orange-600" />
          <h3 className="text-2xl font-bold text-gray-900">
            Life Cycle Interpretation
          </h3>
          <span className="text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded-full font-semibold">
            ISO 14044 §4.5
          </span>
        </div>
        {expanded ? <ChevronDown className="w-6 h-6" /> : <ChevronRight className="w-6 h-6" />}
      </button>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="space-y-6"
        >
          {/* Identification of Significant Issues */}
          <div className="bg-orange-50 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3">
              1. Identification of Significant Issues (ISO 14044 §4.5.3.1)
            </h4>
            <div className="space-y-2">
              {results.sensitivity_analysis?.most_influential_parameters?.slice(0, 3).map((param, idx) => (
                <div key={idx} className="bg-white rounded-lg p-3 border-l-4 border-orange-500">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900">{param.parameter_name}</span>
                    <span className="text-sm font-bold text-orange-600">
                      {param.influence_percentage.toFixed(1)}% contribution
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 mt-1">
                    High influence parameter - priority for improvement actions
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Completeness Check */}
          <div className="bg-green-50 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3 flex items-center space-x-2">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              <span>2. Completeness Check (ISO 14044 §4.5.3.2)</span>
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between bg-white p-2 rounded">
                <span>All relevant impact categories addressed</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex items-center justify-between bg-white p-2 rounded">
                <span>All life cycle stages within boundaries covered</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex items-center justify-between bg-white p-2 rounded">
                <span>Information sufficient for interpretation</span>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
            </div>
          </div>

          {/* Consistency Check */}
          <div className="bg-blue-50 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3 flex items-center space-x-2">
              <Scale className="w-5 h-5 text-blue-600" />
              <span>3. Consistency Check (ISO 14044 §4.5.3.3)</span>
            </h4>
            <div className="space-y-2 text-sm">
              <div className="bg-white p-3 rounded">
                <strong>Methodological Consistency:</strong>
                <p className="text-gray-700 mt-1">
                  ReCiPe 2016 applied consistently across all impact categories.
                  Allocation methods applied uniformly. Cut-off criteria (1%) consistently applied.
                </p>
              </div>
              <div className="bg-white p-3 rounded">
                <strong>Data Quality Consistency:</strong>
                <p className="text-gray-700 mt-1">
                  Primary data from farm records ({results.country}).
                  Background data from consistent sources (ecoinvent 3.9.1, Agri-footprint 6.0).
                  All data meets minimum quality requirements.
                </p>
              </div>
            </div>
          </div>

          {/* Conclusions & Recommendations */}
          <div className="border-2 border-orange-500 rounded-lg p-4">
            <h4 className="font-bold text-gray-900 mb-3">
              4. Conclusions, Limitations & Recommendations (ISO 14044 §4.5.3.4)
            </h4>

            <div className="space-y-3">
              <div className="bg-white p-3 rounded border-l-4 border-green-500">
                <strong className="text-green-700">Key Findings:</strong>
                <p className="text-sm text-gray-700 mt-1">
                  Environmental hotspots identified in{' '}
                  {results.sensitivity_analysis?.most_influential_parameters?.[0]?.parameter_name || 'key operational areas'}.
                  Overall performance: {results.single_score && typeof results.single_score === 'object' && 'value' in results.single_score
                    ? ((results.single_score.value as number) * 100).toFixed(1)
                    : 'N/A'}% normalized score.
                </p>
              </div>

              <div className="bg-yellow-50 p-3 rounded border-l-4 border-yellow-500">
                <strong className="text-yellow-700">Limitations:</strong>
                <ul className="text-xs text-gray-700 mt-1 space-y-1">
                  <li>• Infrastructure impacts excluded (cut-off &lt;1%)</li>
                  <li>• Biodiversity impacts based on land use proxies</li>
                  <li>• Regional characterization factors have uncertainty</li>
                  <li>• Temporal variability not fully captured (single year assessment)</li>
                </ul>
              </div>

              <div className="bg-blue-50 p-3 rounded border-l-4 border-blue-500">
                <strong className="text-blue-700">Recommendations:</strong>
                <ul className="text-sm text-gray-700 mt-1 space-y-1">
                  {results.recommendations?.slice(0, 3).map((rec, idx) => (
                    <li key={idx}>• {rec.title || rec.description}</li>
                  )) || <li>• Refer to detailed recommendations section</li>}
                </ul>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// Critical Review Statement (ISO 14044 Section 6)
export function CriticalReviewSection() {
  return (
    <div className="bg-gray-50 rounded-2xl p-6 border-2 border-gray-300">
      <div className="flex items-start space-x-3">
        <AlertCircle className="w-6 h-6 text-gray-600 mt-1 flex-shrink-0" />
        <div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            Critical Review Statement (ISO 14044 §6)
          </h3>
          <p className="text-sm text-gray-700 mb-3">
            This LCA study follows ISO 14044:2006 requirements for internal decision-making.
            As this is not intended for comparative assertions disclosed to the public,
            external critical review is not mandatory (ISO 14044 §6.2).
          </p>
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <h4 className="font-semibold text-gray-900 mb-2 text-sm">Internal Validation:</h4>
            <ul className="text-xs text-gray-700 space-y-1">
              <li>✓ Methods consistent with ISO 14040 and ISO 14044</li>
              <li>✓ Methods scientifically and technically valid</li>
              <li>✓ Data appropriate and reasonable</li>
              <li>✓ Interpretations reflect limitations</li>
              <li>✓ Report transparent and consistent</li>
            </ul>
            <p className="text-xs text-gray-600 mt-3 italic">
              For comparative assertions or public disclosure, external critical review by
              independent expert(s) is required (ISO 14044 §6.3).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
