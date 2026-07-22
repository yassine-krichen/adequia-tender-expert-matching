import { apiClient } from '@/common/lib/api-client';
import type { CandidateCvExtraction } from '../types/candidate.types';

export function getCandidate(candidateId: string) {
  return apiClient.get<CandidateCvExtraction>(`/candidates/${candidateId}`);
}
