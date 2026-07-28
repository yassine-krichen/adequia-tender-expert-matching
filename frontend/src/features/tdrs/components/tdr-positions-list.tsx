import { Building2, Check, Wrench, X } from 'lucide-react';

import { InfoTooltip } from '@/common/components/info-tooltip';
import { SubScoreBar } from '@/common/components/sub-score-bar';
import { TableLink } from '@/common/components/table-link';
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
import type { MatchResult } from '@/features/matching/types/match.types';
import type { ExpertPositionExtraction } from '@/features/tdrs/types/tdr.types';

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
              <TableLink href={`/matches/${match.match_id}`}>
                {match.candidate_full_name}
              </TableLink>
            </TableCell>
            <TableCell>
              {match.compatibility_score != null
                ? `${Math.round(match.compatibility_score * 100)}%`
                : '—'}
            </TableCell>
            <TableCell>
              {match.hard_filter_passed ? (
                <Badge variant="success-light" className="inline-flex items-center gap-1">
                  <Check className="size-3.5" />
                  Passed
                </Badge>
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="destructive-light" className="inline-flex items-center gap-1">
                      <X className="size-3.5" />
                      Failed
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>{match.hard_filter_failures.join('; ')}</TooltipContent>
                </Tooltip>
              )}
            </TableCell>
            <TableCell>
              {match.sub_scores && (
                <div className="min-w-32 space-y-1">
                  <SubScoreBar
                    icon={Wrench}
                    label="Skill"
                    value={match.sub_scores.skill_score}
                    tooltip="How well the candidate's listed skills cover this position's required skills."
                  />
                  <SubScoreBar
                    icon={Building2}
                    label="Sector"
                    value={match.sub_scores.sector_score}
                    tooltip="How closely the candidate's sector experience matches this position's required sector."
                  />
                </div>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function TdrPositionsList({
  positions,
  matchesByPosition,
}: {
  positions: ExpertPositionExtraction[];
  matchesByPosition?: Record<string, MatchResult[]>;
}) {
  return (
    <div className="space-y-4" data-tour="tdr-positions">
      <h3 className="font-heading text-sm text-muted-foreground">Expert positions</h3>

      {positions.map((position) => (
        <div
          key={position.position_id}
          className="space-y-2 border-t border-border pt-3 sm:grid sm:grid-cols-[minmax(0,320px)_1fr] sm:gap-6 sm:space-y-0"
        >
          <div className="space-y-2">
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
                : {position.required_skills.length > 0 ? position.required_skills.join(', ') : '—'}
              </p>
              <p className="flex items-start gap-1">
                <span className="inline-flex items-center gap-1">
                  Evaluation weight
                  <InfoTooltip text="This position's relative weight in the overall mission evaluation, as stated in the TDR (when specified)." />
                </span>
                : {position.evaluation_weight != null ? position.evaluation_weight : '—'}
              </p>
            </div>
          </div>
          {matchesByPosition?.[position.position_id] && (
            <div data-tour="tdr-matches">
              <PositionMatches matches={matchesByPosition[position.position_id]} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
