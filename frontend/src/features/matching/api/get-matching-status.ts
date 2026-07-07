import { apiClient } from '@/common/lib/api-client';
import type { MatchingStatus } from '../types/match.types';

export function getMatchingStatus(tdrId: string) {
  return apiClient.get<MatchingStatus>(`/tdrs/${tdrId}/match-status`);
}
