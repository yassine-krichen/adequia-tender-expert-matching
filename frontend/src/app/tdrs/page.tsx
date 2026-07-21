'use client';

import { FileText } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import { EmptyState } from '@/common/components/empty-state';
import { FileUpload } from '@/common/components/file-upload';
import { InfoTooltip } from '@/common/components/info-tooltip';
import { SubScoreBar } from '@/common/components/sub-score-bar';
import { Button } from '@/common/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/common/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/common/components/ui/tooltip';
import { Badge } from '@/components/reui/badge';
import { getMatchingStatus } from '@/features/matching/api/get-matching-status';
import { getPositionMatches } from '@/features/matching/api/get-position-matches';
import { runMatching } from '@/features/matching/api/run-matching';
import type { MatchResult, MatchingStatus } from '@/features/matching/types/match.types';
import { getTdr } from '@/features/tdrs/api/get-tdr';
import { getTdrStatus } from '@/features/tdrs/api/get-tdr-status';
import { uploadTdr } from '@/features/tdrs/api/upload-tdr';
import type { TdrExtraction, TdrStatus } from '@/features/tdrs/types/tdr.types';
import { useGuidedTour } from '@/features/tour/use-guided-tour';

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

function describeMatchingProgress(status: MatchingStatus): string {
  if (status.positions_total) {
    return `Matching position ${(status.positions_done ?? 0) + 1} of ${status.positions_total}…`;
  }
  return 'Starting matching…';
}

function PositionMatches({ matches }: { matches: MatchResult[] }) {
  if (matches.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No shortlisted candidates for this position.</p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Candidate</TableHead>
          <TableHead>
            <span className="inline-flex items-center gap-1">
              Compatibility
              <InfoTooltip text="Overall match score combining skill coverage and sector fit against this position's requirements." />
            </span>
          </TableHead>
          <TableHead>
            <span className="inline-flex items-center gap-1">
              Hard filter
              <InfoTooltip text="Whether the candidate meets this position's mandatory requirements (diploma, minimum experience, required certifications). A failed hard filter means the candidate wasn't scored further." />
            </span>
          </TableHead>
          <TableHead>Sub-scores</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {matches.map((match) => (
          <TableRow key={match.match_id}>
            <TableCell>
              <Link href={`/matches/${match.match_id}`}>{match.candidate_full_name}</Link>
            </TableCell>
            <TableCell>
              {match.compatibility_score != null
                ? `${Math.round(match.compatibility_score * 100)}%`
                : '—'}
            </TableCell>
            <TableCell>
              {match.hard_filter_passed ? (
                <Badge variant="success-light">Passed</Badge>
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="destructive-light">Failed</Badge>
                  </TooltipTrigger>
                  <TooltipContent>{match.hard_filter_failures.join('; ')}</TooltipContent>
                </Tooltip>
              )}
            </TableCell>
            <TableCell>
              {match.sub_scores && (
                <div className="min-w-32 space-y-1">
                  <SubScoreBar label="Skill" value={match.sub_scores.skill_score} />
                  <SubScoreBar label="Sector" value={match.sub_scores.sector_score} />
                </div>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
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
    <main className="mx-auto max-w-2xl space-y-6 p-8">
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
              <input
                type="checkbox"
                checked={forceReprocess}
                onChange={(event) => setForceReprocess(event.target.checked)}
                disabled={isUploading}
                className="size-4 rounded border-input"
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

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>{result.mission_title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p>Client: {result.client ?? '—'}</p>
            <p>Sector: {result.sector ?? '—'}</p>

            <div className="space-y-4" data-tour="tdr-positions">
              <div className="flex items-center justify-between">
                <h3 className="font-heading text-sm text-muted-foreground">Expert positions</h3>
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

              {result.positions.map((position) => (
                <div key={position.position_id} className="space-y-2 border-t border-border pt-3">
                  <p>
                    <span className="font-medium">{position.position_title}</span>
                    {position.minimum_years_experience != null &&
                      ` — ${position.minimum_years_experience}+ years`}
                    {position.mandatory_diploma && ` — ${position.mandatory_diploma}`}
                  </p>
                  <div className="space-y-1 text-sm text-muted-foreground">
                    <p className="flex items-start gap-1">
                      <span className="inline-flex items-center gap-1">
                        Required certifications
                        <InfoTooltip text="Certifications this position's TDR explicitly requires — not the candidate's own certifications." />
                      </span>
                      :{' '}
                      {position.required_certifications.length > 0
                        ? position.required_certifications.join(', ')
                        : '—'}
                    </p>
                    <p className="flex items-start gap-1">
                      <span className="inline-flex items-center gap-1">
                        Required languages
                        <InfoTooltip text="Languages and minimum proficiency levels this position's TDR requires." />
                      </span>
                      :{' '}
                      {position.required_languages.length > 0
                        ? position.required_languages
                            .map((lang) => `${lang.language} (${lang.minimum_level})`)
                            .join(', ')
                        : '—'}
                    </p>
                    <p className="flex items-start gap-1">
                      <span className="inline-flex items-center gap-1">
                        Required skills
                        <InfoTooltip text="Skills extracted from the TDR's requirements for this position, used to compute the skill sub-score during matching." />
                      </span>
                      :{' '}
                      {position.required_skills.length > 0
                        ? position.required_skills.join(', ')
                        : '—'}
                    </p>
                    <p className="flex items-start gap-1">
                      <span className="inline-flex items-center gap-1">
                        Evaluation weight
                        <InfoTooltip text="This position's relative weight in the overall mission evaluation, as stated in the TDR (when specified)." />
                      </span>
                      : {position.evaluation_weight != null ? position.evaluation_weight : '—'}
                    </p>
                  </div>
                  {matchingStatus === 'done' && matchesByPosition[position.position_id] && (
                    <div data-tour="tdr-matches">
                      <PositionMatches matches={matchesByPosition[position.position_id]} />
                    </div>
                  )}
                </div>
              ))}
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
