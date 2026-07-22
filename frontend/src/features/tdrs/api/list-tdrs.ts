import { apiClient } from '@/common/lib/api-client';
import type { TdrSummary } from '../types/tdr.types';

export function listTdrs() {
  return apiClient.get<TdrSummary[]>('/tdrs');
}
