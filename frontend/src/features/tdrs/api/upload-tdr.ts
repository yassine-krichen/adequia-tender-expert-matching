import { apiClient } from '@/common/lib/api-client';
import type { TdrUploadAck } from '../types/tdr.types';

export function uploadTdr(file: File, options?: { force?: boolean }) {
  const formData = new FormData();
  formData.append('file', file);
  const path = options?.force ? '/tdrs?force=true' : '/tdrs';
  return apiClient.upload<TdrUploadAck>(path, formData);
}
