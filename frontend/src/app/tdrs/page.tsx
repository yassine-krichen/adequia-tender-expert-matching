'use client';

import { useState } from 'react';

import { Button } from '@/common/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { Input } from '@/common/components/ui/input';
import { uploadTdr } from '@/features/tdrs/api/upload-tdr';
import type { TdrExtraction } from '@/features/tdrs/types/tdr.types';

export default function TdrsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<TdrExtraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    const { data, error: uploadError } = await uploadTdr(file);
    if (uploadError) {
      setError(uploadError);
    } else {
      setResult(data);
    }
    setIsUploading(false);
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
          <form className="flex items-center gap-3" onSubmit={handleSubmit}>
            <Input
              type="file"
              accept=".pdf,.docx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <Button type="submit" disabled={!file || isUploading}>
              {isUploading ? 'Uploading…' : 'Upload'}
            </Button>
          </form>
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
