'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import { getMatch } from '@/features/matching/api/get-match';
import { MatchReportView } from '@/features/matching/components/match-report-view';
import type { MatchDetail } from '@/features/matching/types/match.types';

export default function ReportPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchMatch() {
      setIsLoading(true);
      setError(null);
      const result = await getMatch(matchId);
      if (cancelled) return;
      if (result.error !== null) {
        setError(result.error);
      } else {
        setMatch(result.data);
      }
      setIsLoading(false);
    }

    void fetchMatch();

    return () => {
      cancelled = true;
    };
  }, [matchId]);

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

  if (match === null) {
    return null;
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-8">
      <MatchReportView match={match} />
    </main>
  );
}
