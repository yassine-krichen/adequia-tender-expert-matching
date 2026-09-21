'use client';

import { FileText } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';

import { EmptyState } from '@/common/components/empty-state';
import { FileUpload } from '@/common/components/file-upload';
import { PageTransition } from '@/common/components/page-transition';
import { TableLink } from '@/common/components/table-link';
import { Button } from '@/common/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { Checkbox } from '@/common/components/ui/checkbox';
import { Skeleton } from '@/common/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/common/components/ui/table';
import { Badge } from '@/components/reui/badge';
import { getMatchingStatus } from '@/features/matching/api/get-matching-status';
import { getPositionMatches } from '@/features/matching/api/get-position-matches';
import { runMatching } from '@/features/matching/api/run-matching';
import type { MatchResult, MatchingStatus } from '@/features/matching/types/match.types';
import { getTdr } from '@/features/tdrs/api/get-tdr';
import { getTdrStatus } from '@/features/tdrs/api/get-tdr-status';
import { listTdrs } from '@/features/tdrs/api/list-tdrs';
import { uploadTdr } from '@/features/tdrs/api/upload-tdr';
import { TdrPositionsList } from '@/features/tdrs/components/tdr-positions-list';
import type { TdrExtraction, TdrStatus, TdrSummary } from '@/features/tdrs/types/tdr.types';
import { useGuidedTour } from '@/features/tour/use-guided-tour';

const POLL_INTERVAL_MS = 1500;

const TDR_STATUS_BADGE_VARIANT: Record<
  string,
  'success-light' | 'info-light' | 'destructive-light'
> = {
  done: 'success-light',
  processing: 'info-light',
  failed: 'destructive-light',
};

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

function describeMatchingProgress(status: MatchingStatus): string {
  if (status.positions_total) {
    return `Matching position ${(status.positions_done ?? 0) + 1} of ${status.positions_total}…`;
  }
  return 'Starting matching…';
}

export default function TdrsPage() {
  useGuidedTour();

  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<TdrExtraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [forceReprocess, setForceReprocess] = useState(false);
  const pollHandle = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [matchingStatus, setMatchingStatus] = useState<MatchingStatus['status']>('not_started');
  const [matchingMessage, setMatchingMessage] = useState<string | null>(null);
  const [matchingError, setMatchingError] = useState<string | null>(null);
  const [matchesByPosition, setMatchesByPosition] = useState<Record<string, MatchResult[]>>({});
  const matchPollHandle = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [pastTdrs, setPastTdrs] = useState<TdrSummary[]>([]);
  const [isLoadingPastTdrs, setIsLoadingPastTdrs] = useState(true);
  const [pastTdrsError, setPastTdrsError] = useState<string | null>(null);

  async function loadPastTdrs() {
    setIsLoadingPastTdrs(true);
    const listResult = await listTdrs();
    if (listResult.error !== null) {
      setPastTdrsError(listResult.error);
    } else {
      setPastTdrsError(null);
      setPastTdrs(listResult.data);
    }
    setIsLoadingPastTdrs(false);
  }

  useEffect(() => {
    void loadPastTdrs();
  }, []);

  useEffect(() => {
    return () => {
      if (pollHandle.current) clearTimeout(pollHandle.current);
      if (matchPollHandle.current) clearTimeout(matchPollHandle.current);
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
      // The upload just added or updated a TDR — refetch so the past-TDRs
      // list reflects it immediately instead of waiting for a manual reload.
      await loadPastTdrs();
    }

    pollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
  }

  function stopMatchPolling() {
    if (matchPollHandle.current) {
      clearTimeout(matchPollHandle.current);
      matchPollHandle.current = null;
    }
  }

  async function fetchAllPositionMatches(positions: TdrExtraction['positions']) {
    const results = await Promise.all(
      positions.map((position) => getPositionMatches(position.position_id))
    );
    const byPosition: Record<string, MatchResult[]> = {};
    const failedTitles: string[] = [];
    results.forEach((matchResult, index) => {
      if (matchResult.error === null) {
        byPosition[positions[index].position_id] = matchResult.data;
      } else {
        failedTitles.push(positions[index].position_title);
      }
    });
    setMatchesByPosition(byPosition);
    if (failedTitles.length > 0) {
      setMatchingError(`Failed to load results for: ${failedTitles.join(', ')}`);
    }
  }

  function pollMatchingUntilDone(tdrId: string, positions: TdrExtraction['positions']) {
    async function poll() {
      const statusResult = await getMatchingStatus(tdrId);
      if (statusResult.error !== null) {
        stopMatchPolling();
        setMatchingStatus('failed');
        setMatchingError(statusResult.error);
        return;
      }
      const status = statusResult.data;
      if (status.status === 'processing') {
        setMatchingMessage(describeMatchingProgress(status));
        matchPollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
        return;
      }

      stopMatchPolling();
      setMatchingStatus(status.status);
      if (status.status === 'failed') {
        setMatchingError('Matching failed');
        return;
      }

      await fetchAllPositionMatches(positions);
    }

    matchPollHandle.current = setTimeout(poll, POLL_INTERVAL_MS);
  }

  async function handleRunMatching() {
    if (!result) return;

    setMatchingStatus('processing');
    setMatchingError(null);
    setMatchesByPosition({});
    setMatchingMessage('Starting matching…');

    const runResult = await runMatching(result.tdr_id);
    if (runResult.error !== null) {
      setMatchingStatus('failed');
      setMatchingError(runResult.error);
      return;
    }

    pollMatchingUntilDone(result.tdr_id, result.positions);
  }

  async function submitUpload(fileToUpload: File, force: boolean) {
    setIsUploading(true);
    setError(null);
    setResult(null);
    setStatusMessage('Uploading…');
    stopMatchPolling();
    setMatchingStatus('not_started');
    setMatchingError(null);
    setMatchesByPosition({});

    const uploadResult = await uploadTdr(fileToUpload, { force });
    if (uploadResult.error !== null) {
      setError(uploadResult.error);
      setIsUploading(false);
      return;
    }

    setStatusMessage('Starting…');
    pollUntilDone(uploadResult.data.tdr_id);
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    void submitUpload(file, forceReprocess);
  }

  function handleRetryWithForce() {
    if (!file) return;
    setForceReprocess(true);
    void submitUpload(file, true);
  }

  return (
    <PageTransition>
      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <h1 className="font-heading text-2xl">TDR upload</h1>
        <p className="text-muted-foreground">
          Upload a TDR (PDF or docx) to see its mission, client, and expert positions extracted.
        </p>

        <Card data-tour="tdr-upload">
          <CardHeader>
            <CardTitle>Upload TDR</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={handleSubmit}>
              <FileUpload accept=".pdf,.docx" disabled={isUploading} onFileSelected={setFile} />
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Checkbox
                  checked={forceReprocess}
                  onCheckedChange={(checked) => setForceReprocess(checked === true)}
                  disabled={isUploading}
                />
                Force reprocess (re-run extraction even if this exact file was already processed)
              </label>
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
          <div className="space-y-2">
            <p role="alert" className="text-destructive">
              {error}
            </p>
            {file && (
              <Button type="button" size="sm" variant="outline" onClick={handleRetryWithForce}>
                Retry with force reprocess
              </Button>
            )}
          </div>
        )}

        {!result && !isUploading && !error && (
          <div className="grid gap-4 sm:grid-cols-2">
            <EmptyState
              icon={FileText}
              title="No expert positions yet"
              description="Upload a TDR above to see its mission and expert positions extracted here."
              data-tour="tdr-positions"
            />
            <EmptyState
              icon={FileText}
              title="No matches yet"
              description="Once a TDR is uploaded, run matching to see shortlisted candidates for each position here."
              data-tour="tdr-matches"
            />
          </div>
        )}

        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <Card>
                <CardHeader>
                  <CardTitle>{result.mission_title}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p>Client: {result.client ?? '—'}</p>
                  <p>Sector: {result.sector ?? '—'}</p>

                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      onClick={handleRunMatching}
                      disabled={matchingStatus === 'processing'}
                    >
                      {matchingStatus === 'processing' ? 'Matching…' : 'Run matching'}
                    </Button>
                  </div>
                  {matchingStatus === 'processing' && matchingMessage && (
                    <p className="text-sm text-muted-foreground" role="status">
                      {matchingMessage}
                    </p>
                  )}
                  {matchingError && (
                    <p role="alert" className="text-sm text-destructive">
                      {matchingError}
                    </p>
                  )}

                  <TdrPositionsList
                    positions={result.positions}
                    matchesByPosition={matchingStatus === 'done' ? matchesByPosition : undefined}
                  />

                  <details>
                    <summary className="cursor-pointer text-muted-foreground">Raw JSON</summary>
                    <pre className="overflow-x-auto text-xs">{JSON.stringify(result, null, 2)}</pre>
                  </details>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        <Card>
          <CardHeader>
            <CardTitle>Past TDRs</CardTitle>
          </CardHeader>
          <CardContent>
            {pastTdrsError && (
              <p role="alert" className="text-destructive">
                {pastTdrsError}
              </p>
            )}
            {!pastTdrsError && isLoadingPastTdrs && (
              <Table role="status" aria-label="Loading past TDRs">
                <TableHeader>
                  <TableRow>
                    <TableHead>Mission</TableHead>
                    <TableHead className="w-28">Status</TableHead>
                    <TableHead className="w-44">Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[0, 1, 2].map((row) => (
                    <TableRow key={row}>
                      <TableCell>
                        <Skeleton className="h-4 w-48" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-16" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-32" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            {!pastTdrsError && !isLoadingPastTdrs && pastTdrs.length === 0 && (
              <EmptyState
                icon={FileText}
                title="No TDRs yet"
                description="Upload a TDR above to see it appear here."
              />
            )}
            {!pastTdrsError && !isLoadingPastTdrs && pastTdrs.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Mission</TableHead>
                    <TableHead className="w-28 whitespace-nowrap">Status</TableHead>
                    <TableHead className="w-44 whitespace-nowrap">Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pastTdrs.map((tdr) => (
                    <TableRow key={tdr.tdr_id}>
                      <TableCell className="max-w-[280px]">
                        <TableLink
                          href={`/tdrs/${tdr.tdr_id}`}
                          className="max-w-full"
                          title={tdr.mission_title ?? undefined}
                        >
                          {tdr.mission_title ?? '—'}
                        </TableLink>
                      </TableCell>
                      <TableCell className="w-28 whitespace-nowrap">
                        <Badge variant={TDR_STATUS_BADGE_VARIANT[tdr.status] ?? 'outline'}>
                          {tdr.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="w-44 whitespace-nowrap">
                        {new Date(tdr.created_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </main>
    </PageTransition>
  );
}
