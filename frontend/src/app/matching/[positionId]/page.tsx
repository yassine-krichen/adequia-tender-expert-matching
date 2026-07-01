export function MatchingResultsPage({ params }: { params: { positionId: string } }) {
  return <main>Ranked candidates for position {params.positionId}.</main>;
}

export default MatchingResultsPage;
