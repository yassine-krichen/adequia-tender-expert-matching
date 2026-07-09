import { apiClient } from '@/common/lib/api-client';
import type { CandidateCvExtraction } from '../types/candidate.types';

export function uploadCv(file: File, options?: { force?: boolean }) {
  const formData = new FormData();
  formData.append('file', file);
  const path = options?.force ? '/candidates/cv?force=true' : '/candidates/cv';
  return apiClient.upload<CandidateCvExtraction>(path, formData);
}
