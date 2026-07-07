import { apiClient } from '@/common/lib/api-client';
import type { MatchResult } from '../types/match.types';

export function getPositionMatches(positionId: string) {
  return apiClient.get<MatchResult[]>(`/positions/${positionId}/matches`);
}
