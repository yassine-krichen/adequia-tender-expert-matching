'use client';

import { BarChart3, FileText, Users } from 'lucide-react';
import { motion } from 'motion/react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { PageTransition } from '@/common/components/page-transition';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { Skeleton } from '@/common/components/ui/skeleton';
import { describePoolSize, describeTdrVolume } from '@/common/lib/describe-count';
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
    <PageTransition>
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <div>
          <h1 className="font-heading text-2xl">Your workspace</h1>
          <p className="text-muted-foreground">
            Current candidate and TDR counts, and quick links into each workflow.
          </p>
          <Link href="/about" className="text-sm font-medium text-primary hover:underline">
            Learn more about AdéquIA →
          </Link>
        </div>

        {isLoading && (
          <div className="grid gap-4 sm:grid-cols-2" role="status" aria-label="Loading workspace">
            <Card>
              <CardHeader>
                <Skeleton className="h-5 w-24" />
              </CardHeader>
              <CardContent className="space-y-2">
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-4 w-40" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Skeleton className="h-5 w-16" />
              </CardHeader>
              <CardContent className="space-y-2">
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-4 w-40" />
              </CardContent>
            </Card>
          </div>
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
                <CardTitle className="flex items-center gap-1.5">
                  <Users className="size-4 text-primary" />
                  Candidates
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                <p className="text-3xl font-semibold">{candidateCount} candidates</p>
                <p className="text-sm text-muted-foreground">
                  {describePoolSize(candidateCount ?? 0)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-1.5">
                  <FileText className="size-4 text-primary" />
                  TDRs
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                <p className="text-3xl font-semibold">{tdrCount} TDRs</p>
                <p className="text-sm text-muted-foreground">{describeTdrVolume(tdrCount ?? 0)}</p>
              </CardContent>
            </Card>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          {QUICK_LINKS.map(({ href, icon: Icon, title, description }) => (
            <Link key={href} href={href}>
              <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }} className="h-full">
                <Card className="h-full transition-colors hover:bg-muted">
                  <CardContent className="flex flex-col items-start gap-2 py-6">
                    <Icon className="size-6 text-primary" />
                    <p className="font-medium">{title}</p>
                    <p className="text-sm text-muted-foreground">{description}</p>
                  </CardContent>
                </Card>
              </motion.div>
            </Link>
          ))}
        </div>
      </main>
    </PageTransition>
  );
}
