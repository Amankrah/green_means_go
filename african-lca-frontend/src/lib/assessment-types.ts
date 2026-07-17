// Which assessment types each role can start, in one place. This mirrors the backend
// role gates: /assess only requires a login, while /processing/assess is limited to
// processors and researchers (see app/processing/routes.py). Keep the two in step —
// widening a role here without widening it there just yields a 403 in the UI.

import type { UserRole } from '@/lib/auth-storage';

export type AssessmentKind = 'farm' | 'processing';

export interface AssessmentTypeOption {
  kind: AssessmentKind;
  href: string;
  label: string;
  description: string;
}

const FARM: AssessmentTypeOption = {
  kind: 'farm',
  href: '/assessment',
  label: 'Farm assessment',
  description: 'Crops, land and on-farm inputs',
};

const PROCESSING: AssessmentTypeOption = {
  kind: 'processing',
  href: '/processing-assessment',
  label: 'Processing assessment',
  description: 'Facilities, energy and throughput',
};

export function assessmentTypesForRole(role: UserRole | undefined): AssessmentTypeOption[] {
  switch (role) {
    case 'processor':
      return [PROCESSING];
    case 'researcher':
      return [FARM, PROCESSING];
    case 'farmer':
    case 'extension_officer':
      return [FARM];
    default:
      return [];
  }
}
