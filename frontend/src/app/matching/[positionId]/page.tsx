export default async function MatchingResultsPage({
  params,
}: {
  params: Promise<{ positionId: string }>;
}) {
  const { positionId } = await params;
  return <main>Ranked candidates for position {positionId}.</main>;
}
