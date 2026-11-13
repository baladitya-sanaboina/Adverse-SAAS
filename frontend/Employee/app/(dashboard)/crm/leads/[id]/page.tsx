import { CrmPipelinePage } from "@/components/crm/crm-pipeline-page";

export default async function LeadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CrmPipelinePage initialEntity={{ type: "lead", id }} />;
}
