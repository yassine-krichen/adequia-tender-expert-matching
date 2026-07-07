import { apiClient } from '@/common/lib/api-client';
import type { TdrExtraction } from '../types/tdr.types';

export function getTdr(tdrId: string) {
  return apiClient.get<TdrExtraction>(`/tdrs/${tdrId}`);
}
