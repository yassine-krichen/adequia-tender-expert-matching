export type Citation = {
  claim: string;
  sourceDoc: 'cv' | 'tdr';
  sourceSpan: string;
};

export type Report = {
  matchId: string;
  rationale: string;
  citations: Citation[];
};
