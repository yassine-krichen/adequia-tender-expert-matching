import { apiClient } from '@/common/lib/api-client';
import type { TdrUploadAck } from '../types/tdr.types';

export function uploadTdr(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.upload<TdrUploadAck>('/tdrs', formData);
}
