export default async function ReportPage({
  params,
}: {
  params: Promise<{ matchId: string }>;
}) {
  const { matchId } = await params;
  return <main>Full report for match {matchId} — rationale, citations, review controls.</main>;
}
