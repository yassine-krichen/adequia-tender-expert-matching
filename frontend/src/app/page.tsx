'use client';

import { BarChart3, FileText, Users } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { fetchCandidates } from '@/features/candidates/api/fetch-candidates';
import { listTdrs } from '@/features/tdrs/api/list-tdrs';

const QUICK_LINKS = [
  {
    href: '/tdrs',
    icon: FileText,
    title: 'Upload TDR',
    description: 'Extract mission, client, and expert positions from a TDR document.',
  },
  {
    href: '/candidates',
    icon: Users,
    title: 'Upload candidate',
    description: 'Turn a CV into structured, extracted data.',
  },
  {
    href: '/metrics',
    icon: BarChart3,
    title: 'View metrics',
    description: 'See eval harness results for extraction, matching, and report quality.',
  },
];

export default function Home() {
  const [candidateCount, setCandidateCount] = useState<number | null>(null);
  const [tdrCount, setTdrCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchCounts() {
      setIsLoading(true);
      setError(null);
      const [candidatesResult, tdrsResult] = await Promise.all([fetchCandidates(), listTdrs()]);
      if (cancelled) return;

      if (candidatesResult.error !== null || tdrsResult.error !== null) {
        setError(candidatesResult.error ?? tdrsResult.error);
      } else {
        setCandidateCount(candidatesResult.data.length);
        setTdrCount(tdrsResult.data.length);
      }
      setIsLoading(false);
    }

    void fetchCounts();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <div>
        <h1 className="font-heading text-2xl">AdéquIA</h1>
        <p className="text-muted-foreground">
          AI-assisted matching between TDR expert positions and candidate CVs.
        </p>
      </div>

      {isLoading && (
        <p className="text-muted-foreground" role="status">
          Loading…
        </p>
      )}

      {error !== null && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}

      {!isLoading && error === null && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Candidates</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold">{candidateCount} candidates</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>TDRs</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold">{tdrCount} TDRs</p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        {QUICK_LINKS.map(({ href, icon: Icon, title, description }) => (
          <Link key={href} href={href}>
            <Card className="h-full transition-colors hover:bg-muted">
              <CardContent className="flex flex-col items-start gap-2 py-6">
                <Icon className="size-6 text-primary" />
                <p className="font-medium">{title}</p>
                <p className="text-sm text-muted-foreground">{description}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
