'use client';

import { useState } from 'react';

import { SubScoreBar } from '@/common/components/sub-score-bar';
import { Button } from '@/common/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/common/components/ui/card';
import { Textarea } from '@/common/components/ui/textarea';
import { Badge } from '@/components/reui/badge';
import { getMatch } from '@/features/matching/api/get-match';
import { submitReview } from '@/features/matching/api/submit-review';
import type {
  Anomaly,
  MatchDetail,
  ReviewDecisionRequest,
} from '@/features/matching/types/match.types';

const SEVERITY_ORDER: Record<Anomaly['severity'], number> = { blocking: 0, warning: 1, info: 2 };

const SEVERITY_BADGE_VARIANT: Record<
  Anomaly['severity'],
  'destructive-light' | 'warning-light' | 'info-light'
> = {
  blocking: 'destructive-light',
  warning: 'warning-light',
  info: 'info-light',
};

const DECISION_LABEL: Record<string, string> = {
  approved: 'Approved',
  rejected: 'Rejected',
  overridden_to_approve: 'Overridden to approve',
  overridden_to_reject: 'Overridden to reject',
};

function sortedAnomalies(anomalies: Anomaly[]): Anomaly[] {
  return [...anomalies].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
}

// The API only surfaces the backend's raw domain-error message (no status
// code -- see ApiResult in api-client.ts), so these two rare, internally-
// phrased messages are pattern-matched here and swapped for reviewer-facing
// copy. The raw message is still logged for debugging. Every other error
// (404, already-reviewed 409, 422) reads fine for a reviewer as-is.
function toReviewerFacingError(rawMessage: string): string {
  if (rawMessage.includes('No pending human_review interrupt')) {
    console.error('submitReview failed:', rawMessage);
    return "This match isn't awaiting review right now — it may have already been processed. Try refreshing the page.";
  }
  if (rawMessage.includes('Failed to persist review decision')) {
    console.error('submitReview failed:', rawMessage);
    return 'Something went wrong saving your review. Your decision may have gone through — click Retry to confirm or resubmit.';
  }
  return rawMessage;
}

export function MatchReportView({ match }: { match: MatchDetail }) {
  const [matchState, setMatchState] = useState(match);
  const [mode, setMode] = useState<'normal' | 'override'>('normal');
  const [overrideDirection, setOverrideDirection] = useState<'approve' | 'reject'>('approve');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastAttempt, setLastAttempt] = useState<ReviewDecisionRequest | null>(null);

  async function submitDecision(
    decision: ReviewDecisionRequest['decision'],
    noteValue: string | null
  ) {
    setSubmitting(true);
    setError(null);
    setLastAttempt({ decision, note: noteValue });

    const result = await submitReview(matchState.match_id, { decision, note: noteValue });
    if (result.error !== null) {
      // The submission may have actually landed server-side (already-reviewed
      // conflict, or a persistence failure after the checkpoint was already
      // resumed) -- refetch to check before surfacing the error as-is.
      const refetched = await getMatch(matchState.match_id);
      if (refetched.error === null && refetched.data.reviewer_decision !== null) {
        setMatchState(refetched.data);
      } else {
        setError(toReviewerFacingError(result.error));
      }
      setSubmitting(false);
      return;
    }

    setMatchState(result.data);
    setSubmitting(false);
  }

  function handleApprove() {
    void submitDecision('approved', null);
  }

  function handleReject() {
    void submitDecision('rejected', null);
  }

  function handleOverrideSubmit() {
    if (!note.trim()) return;
    void submitDecision(
      overrideDirection === 'approve' ? 'overridden_to_approve' : 'overridden_to_reject',
      note
    );
  }

  function handleRetry() {
    if (!lastAttempt) return;
    void submitDecision(lastAttempt.decision, lastAttempt.note);
  }

  const anomalies = sortedAnomalies(matchState.anomalies);

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-2xl">Match report</h1>

      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Hard filter:</span>
            {matchState.hard_filter_passed ? (
              <Badge variant="success-light">Passed</Badge>
            ) : (
              <Badge variant="destructive-light">Failed</Badge>
            )}
          </div>
          {!matchState.hard_filter_passed && matchState.hard_filter_failures.length > 0 && (
            <ul className="list-inside list-disc text-sm text-muted-foreground">
              {matchState.hard_filter_failures.map((failure) => (
                <li key={failure}>{failure}</li>
              ))}
            </ul>
          )}

          <p>
            <span className="text-muted-foreground">Compatibility score: </span>
            {matchState.compatibility_score != null
              ? `${Math.round(matchState.compatibility_score * 100)}%`
              : '—'}
          </p>

          {matchState.sub_scores && (
            <div className="max-w-sm space-y-1">
              <SubScoreBar label="Education" value={matchState.sub_scores.education_score ?? 0} />
              <SubScoreBar label="Experience" value={matchState.sub_scores.experience_score ?? 0} />
              <SubScoreBar
                label="Certification"
                value={matchState.sub_scores.certification_score ?? 0}
              />
              <SubScoreBar label="Sector" value={matchState.sub_scores.sector_score} />
              <SubScoreBar label="Language" value={matchState.sub_scores.language_score ?? 0} />
              <SubScoreBar label="Skill" value={matchState.sub_scores.skill_score} />
              <SubScoreBar
                label="Qualitative fit"
                value={matchState.sub_scores.qualitative_fit_score ?? 0}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Rationale</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p>{matchState.rationale ?? '—'}</p>

          {matchState.citations.length > 0 && (
            <details>
              <summary className="cursor-pointer text-muted-foreground">
                Citations ({matchState.citations.length})
              </summary>
              <ul className="mt-2 space-y-2 text-sm">
                {matchState.citations.map((citation, index) => (
                  <li key={index} className="border-t border-border pt-2">
                    <p className="font-medium">{citation.claim}</p>
                    <p className="text-muted-foreground">
                      {citation.source_doc}: {citation.source_span}
                    </p>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Anomalies</CardTitle>
        </CardHeader>
        <CardContent>
          {anomalies.length === 0 ? (
            <p className="text-sm text-muted-foreground">No anomalies detected.</p>
          ) : (
            <ul className="space-y-2">
              {anomalies.map((anomaly, index) => (
                <li key={index}>
                  <details>
                    <summary className="flex cursor-pointer items-center gap-2 text-sm">
                      <Badge variant={SEVERITY_BADGE_VARIANT[anomaly.severity]}>
                        {anomaly.severity}
                      </Badge>
                      {anomaly.description}
                    </summary>
                    <p className="mt-1 pl-1 text-sm text-muted-foreground">
                      {anomaly.source_citation}
                    </p>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Review</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">Reviewed anonymously — no login yet.</p>

          {matchState.reviewer_decision !== null ? (
            <p role="status">
              Reviewed:{' '}
              {DECISION_LABEL[matchState.reviewer_decision] ?? matchState.reviewer_decision}
              {matchState.reviewer_note && (
                <span className="block text-sm text-muted-foreground">
                  Note: {matchState.reviewer_note}
                </span>
              )}
            </p>
          ) : (
            <div className="space-y-3">
              {mode === 'normal' ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="button" onClick={handleApprove} disabled={submitting}>
                    Approve
                  </Button>
                  <Button
                    type="button"
                    variant="destructive"
                    onClick={handleReject}
                    disabled={submitting}
                  >
                    Reject
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setMode('override')}
                    disabled={submitting}
                  >
                    Override
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-4 text-sm">
                    <label className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        name="override-direction"
                        checked={overrideDirection === 'approve'}
                        onChange={() => setOverrideDirection('approve')}
                      />
                      Approve anyway
                    </label>
                    <label className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        name="override-direction"
                        checked={overrideDirection === 'reject'}
                        onChange={() => setOverrideDirection('reject')}
                      />
                      Reject anyway
                    </label>
                  </div>
                  <Textarea
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="Explain why you're overriding the automated assessment (required)"
                    disabled={submitting}
                  />
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      onClick={handleOverrideSubmit}
                      disabled={submitting || !note.trim()}
                    >
                      Submit override
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setMode('normal');
                        setNote('');
                      }}
                      disabled={submitting}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="space-y-2">
              <p role="alert" className="text-destructive">
                {error}
              </p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleRetry}
                disabled={submitting}
              >
                Retry
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
