export type ExpertPosition = {
  positionId: string;
  positionTitle: string;
  mandatoryDiploma: string | null;
  minimumYearsExperience: number | null;
};

export type Tdr = {
  tdrId: string;
  missionTitle: string;
  client: string | null;
  sector: string | null;
  positions: ExpertPosition[];
};
