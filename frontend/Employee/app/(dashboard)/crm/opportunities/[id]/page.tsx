import { CrmPipelinePage } from "@/components/crm/crm-pipeline-page";

export default async function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CrmPipelinePage initialEntity={{ type: "opportunity", id }} />;
}
