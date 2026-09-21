'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import { BackLink } from '@/common/components/back-link';
import { DetailPageSkeleton } from '@/common/components/detail-page-skeleton';
import { PageTransition } from '@/common/components/page-transition';
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

  if (match === null) {
    return null;
  }

  return (
    <PageTransition>
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <BackLink href={`/tdrs/${match.tdr_id}`} label={`Back to ${match.tdr_mission_title}`} />
        <MatchReportView match={match} />
      </main>
    </PageTransition>
  );
}
