export function TdrDetailPage({ params }: { params: { tdrId: string } }) {
  return <main>TDR {params.tdrId} — extracted positions and requirements.</main>;
}

export default TdrDetailPage;
