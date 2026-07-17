import { apiClient } from '@/common/lib/api-client';
import type { MatchDetail } from '../types/match.types';

export function getMatch(matchId: string) {
  return apiClient.get<MatchDetail>(`/matches/${matchId}`);
}
