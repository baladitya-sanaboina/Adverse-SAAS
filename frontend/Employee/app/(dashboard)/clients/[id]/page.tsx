import { ClientManagementPage } from "@/components/clients/client-management-page";

export default async function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ClientManagementPage initialClientId={id} />;
}
