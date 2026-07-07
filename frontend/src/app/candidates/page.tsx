'use client';

import { useState } from 'react';

import { FileUpload } from '@/common/components/file-upload';
import { Button } from '@/common/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { uploadCv } from '@/features/candidates/api/upload-cv';
import type { CandidateCvExtraction } from '@/features/candidates/types/candidate.types';

export default function CandidatesPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<CandidateCvExtraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    const uploadResult = await uploadCv(file);
    if (uploadResult.error !== null) {
      setError(uploadResult.error);
    } else {
      setResult(uploadResult.data);
    }
    setIsUploading(false);
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <h1 className="font-heading text-2xl">Candidate CV upload</h1>
      <p className="text-muted-foreground">
        Upload a CV (PDF or docx) to see it turned into structured, extracted data.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Upload CV</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={handleSubmit}>
            <FileUpload accept=".pdf,.docx" disabled={isUploading} onFileSelected={setFile} />
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
            <CardTitle>{result.full_name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p>Total years of experience: {result.total_years_experience}</p>

            <div>
              <h3 className="font-heading text-sm text-muted-foreground">Education</h3>
              <ul className="list-inside list-disc">
                {result.education.map((edu) => (
                  <li key={edu.source_span}>
                    {edu.degree}
                    {edu.field && ` in ${edu.field}`} — {edu.institution}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="font-heading text-sm text-muted-foreground">Experience</h3>
              <ul className="list-inside list-disc">
                {result.experience.map((exp) => (
                  <li key={exp.source_span}>
                    {exp.title} — {exp.employer} ({exp.start_date} to {exp.end_date ?? 'present'})
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="font-heading text-sm text-muted-foreground">Skills</h3>
              <p>{result.raw_skills.join(', ')}</p>
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
