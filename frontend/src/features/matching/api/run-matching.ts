import { apiClient } from '@/common/lib/api-client';

export function runMatching(tdrId: string) {
  return apiClient.post<null>(`/tdrs/${tdrId}/match`);
}
