export default async function TdrDetailPage({
  params,
}: {
  params: Promise<{ tdrId: string }>;
}) {
  const { tdrId } = await params;
  return <main>TDR {tdrId} — extracted positions and requirements.</main>;
}
