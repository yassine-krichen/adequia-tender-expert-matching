import { apiClient } from '@/common/lib/api-client';
import type { Candidate } from '../types/candidate.types';

export function fetchCandidates() {
  return apiClient.get<Candidate[]>('/candidates');
}
