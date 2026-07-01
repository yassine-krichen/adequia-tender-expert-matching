export type SubScores = {
  educationScore: number;
  experienceScore: number;
  certificationScore: number;
  sectorScore: number;
  languageScore: number;
  skillScore: number;
};

export type MatchResult = {
  matchId: string;
  cvId: string;
  positionId: string;
  hardFilterPassed: boolean;
  compatibilityScore: number | null;
  subScores: SubScores | null;
};
