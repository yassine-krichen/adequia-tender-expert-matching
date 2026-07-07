'use client';

import { useEffect, useRef, useState } from 'react';

import { FileUpload } from '@/common/components/file-upload';
import { Button } from '@/common/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { getTdr } from '@/features/tdrs/api/get-tdr';
import { getTdrStatus } from '@/features/tdrs/api/get-tdr-status';
import { uploadTdr } from '@/features/tdrs/api/upload-tdr';
import type { TdrExtraction, TdrStatus } from '@/features/tdrs/types/tdr.types';

const POLL_INTERVAL_MS = 1500;

function describeStep(status: TdrStatus): string {
  switch (status.step) {
    case 'parsing':
      return 'Parsing document…';
    case 'retrieving':
      return 'Locating the relevant section…';
    case 'extracting':
      return status.chunks_total
        ? `Extracting section ${(status.chunks_done ?? 0) + 1} of ${status.chunks_total}…`
        : 'Extracting…';
    case 'merging':
      return 'Combining results…';
    default:
      return 'Starting…';
  }
}

export default function TdrsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<TdrExtraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const pollHandle = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pollHandle.current) clearTimeout(pollHandle.current);
    };
  }, []);

  function stopPolling() {
    if (pollHandle.current) {
      clearTimeout(pollHandle.current);
      pollHandle.current = null;
    }
  }

  function pollUntilDone(tdrId: string) {
    // setTimeout, not setInterval: the next poll is only scheduled after
    // the current one resolves, so a slow request can't fire an
    // overlapping one.
    async function poll() {
      const statusResult = await getTdrStatus(tdrId);
      if (statusResult.error !== null) {
        stopPolling();
        setError(statusResult.error);
        setIsUploading(false);
        return;
      }
      const status = statusResult.data;
      if (status.status === 'processing') {
        setStatusMessage(describeStep(status));
        pollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
        return;
      }

      stopPolling();
      if (status.status === 'failed') {
        setError(status.error_message ?? 'TDR extraction failed');
        setIsUploading(false);
        return;
      }

      const tdrResult = await getTdr(tdrId);
      setIsUploading(false);
      if (tdrResult.error !== null) {
        setError(tdrResult.error);
      } else {
        setResult(tdrResult.data);
      }
    }

    pollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);
    setStatusMessage('Uploading…');

    const uploadResult = await uploadTdr(file);
    if (uploadResult.error !== null) {
      setError(uploadResult.error);
      setIsUploading(false);
      return;
    }

    setStatusMessage('Starting…');
    pollUntilDone(uploadResult.data.tdr_id);
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <h1 className="font-heading text-2xl">TDR upload</h1>
      <p className="text-muted-foreground">
        Upload a TDR (PDF or docx) to see its mission, client, and expert positions extracted.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Upload TDR</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={handleSubmit}>
            <FileUpload accept=".pdf,.docx" disabled={isUploading} onFileSelected={setFile} />
            <Button type="submit" disabled={!file || isUploading}>
              {isUploading ? 'Uploading…' : 'Upload'}
            </Button>
          </form>
          {isUploading && statusMessage && (
            <p className="mt-3 text-sm text-muted-foreground" role="status">
              {statusMessage}
            </p>
          )}
        </CardContent>
      </Card>

      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>{result.mission_title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p>Client: {result.client ?? '—'}</p>
            <p>Sector: {result.sector ?? '—'}</p>

            <div>
              <h3 className="font-heading text-sm text-muted-foreground">Expert positions</h3>
              <ul className="list-inside list-disc">
                {result.positions.map((position) => (
                  <li key={position.position_id}>
                    {position.position_title}
                    {position.minimum_years_experience != null &&
                      ` — ${position.minimum_years_experience}+ years`}
                    {position.mandatory_diploma && ` — ${position.mandatory_diploma}`}
                  </li>
                ))}
              </ul>
            </div>

            <details>
              <summary className="cursor-pointer text-muted-foreground">Raw JSON</summary>
              <pre className="overflow-x-auto text-xs">{JSON.stringify(result, null, 2)}</pre>
            </details>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
