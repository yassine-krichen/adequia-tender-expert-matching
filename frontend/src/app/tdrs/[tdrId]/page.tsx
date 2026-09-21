'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import { BackLink } from '@/common/components/back-link';
import { DetailPageSkeleton } from '@/common/components/detail-page-skeleton';
import { PageTransition } from '@/common/components/page-transition';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { getPositionMatches } from '@/features/matching/api/get-position-matches';
import type { MatchResult } from '@/features/matching/types/match.types';
import { getTdr } from '@/features/tdrs/api/get-tdr';
import { TdrPositionsList } from '@/features/tdrs/components/tdr-positions-list';
import type { TdrExtraction } from '@/features/tdrs/types/tdr.types';

export default function TdrDetailPage() {
  const { tdrId } = useParams<{ tdrId: string }>();
  const [tdr, setTdr] = useState<TdrExtraction | null>(null);
  const [matchesByPosition, setMatchesByPosition] = useState<Record<string, MatchResult[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchTdrAndMatches() {
      setIsLoading(true);
      setError(null);
      const result = await getTdr(tdrId);
      if (cancelled) return;
      if (result.error !== null) {
        setError(result.error);
        setIsLoading(false);
        return;
      }
      setTdr(result.data);
      setIsLoading(false);

      // Best-effort: a position with no matching run yet just renders
      // empty here, no error surfaced -- this page is read-only history,
      // not a place to prompt for a re-run.
      const matchResults = await Promise.all(
        result.data.positions.map((position) => getPositionMatches(position.position_id))
      );
      if (cancelled) return;
      const byPosition: Record<string, MatchResult[]> = {};
      matchResults.forEach((matchResult, index) => {
        if (matchResult.error === null) {
          byPosition[result.data.positions[index].position_id] = matchResult.data;
        }
      });
      setMatchesByPosition(byPosition);
    }

    void fetchTdrAndMatches();

    return () => {
      cancelled = true;
    };
  }, [tdrId]);

  if (isLoading) {
    return (
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <BackLink href="/tdrs" label="Back to TDRs" />
        <DetailPageSkeleton />
      </main>
    );
  }

  if (error !== null) {
    return (
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <BackLink href="/tdrs" label="Back to TDRs" />
        <p role="alert" className="text-destructive">
          {error}
        </p>
      </main>
    );
  }

  if (tdr === null) {
    return null;
  }

  return (
    <PageTransition>
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <BackLink href="/tdrs" label="Back to TDRs" />
        <Card>
          <CardHeader>
            <CardTitle>{tdr.mission_title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p>Client: {tdr.client ?? '—'}</p>
            <p>Sector: {tdr.sector ?? '—'}</p>

            <TdrPositionsList positions={tdr.positions} matchesByPosition={matchesByPosition} />
          </CardContent>
        </Card>
      </main>
    </PageTransition>
  );
}
