export function ReportPage({ params }: { params: { matchId: string } }) {
  return <main>Full report for match {params.matchId} — rationale, citations, review controls.</main>;
}

export default ReportPage;
