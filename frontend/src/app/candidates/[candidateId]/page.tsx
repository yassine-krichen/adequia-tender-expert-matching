'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import { getCandidate } from '@/features/candidates/api/get-candidate';
import { CandidateCvDetail } from '@/features/candidates/components/candidate-cv-detail';
import type { CandidateCvExtraction } from '@/features/candidates/types/candidate.types';

export default function CandidateDetailPage() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const [cv, setCv] = useState<CandidateCvExtraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchCandidate() {
      setIsLoading(true);
      setError(null);
      const result = await getCandidate(candidateId);
      if (cancelled) return;
      if (result.error !== null) {
        setError(result.error);
      } else {
        setCv(result.data);
      }
      setIsLoading(false);
    }

    void fetchCandidate();

    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  if (isLoading) {
    return (
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <p className="text-muted-foreground" role="status">
          Loading…
        </p>
      </main>
    );
  }

  if (error !== null) {
    return (
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <p role="alert" className="text-destructive">
          {error}
        </p>
      </main>
    );
  }

  if (cv === null) {
    return null;
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-8">
      <CandidateCvDetail cv={cv} />
    </main>
  );
}
