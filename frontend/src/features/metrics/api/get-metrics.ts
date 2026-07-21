import { apiClient } from '@/common/lib/api-client';
import type { MetricsSnapshot } from '../types/metrics.types';

export function getMetrics() {
  return apiClient.get<MetricsSnapshot>('/metrics');
}
