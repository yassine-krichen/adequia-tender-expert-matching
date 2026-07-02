import { apiClient } from '@/common/lib/api-client';
import type { TdrExtraction } from '../types/tdr.types';

export function uploadTdr(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.upload<TdrExtraction>('/tdrs', formData);
}
