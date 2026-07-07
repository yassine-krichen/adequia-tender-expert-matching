import { apiClient } from '@/common/lib/api-client';
import type { TdrStatus } from '../types/tdr.types';

export function getTdrStatus(tdrId: string) {
  return apiClient.get<TdrStatus>(`/tdrs/${tdrId}/status`);
}
