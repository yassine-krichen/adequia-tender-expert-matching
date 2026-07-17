import { apiClient } from '@/common/lib/api-client';
import type { MatchDetail, ReviewDecisionRequest } from '../types/match.types';

export function submitReview(matchId: string, body: ReviewDecisionRequest) {
  return apiClient.post<MatchDetail>(`/matches/${matchId}/review`, body);
}
