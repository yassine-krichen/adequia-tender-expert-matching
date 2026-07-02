import { apiClient } from '@/common/lib/api-client';
import type { CandidateCvExtraction } from '../types/candidate.types';

export function uploadCv(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.upload<CandidateCvExtraction>('/candidates/cv', formData);
}
