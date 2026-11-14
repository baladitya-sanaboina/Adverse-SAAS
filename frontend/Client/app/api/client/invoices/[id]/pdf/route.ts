import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

type Context = { params: Promise<{ id: string }> };

// The client's own sent invoice as a PDF (the backend checks ownership and status).
export async function GET(request: NextRequest, context: Context) {
  const { id } = await context.params;
  return proxyToBackend(request, "/client-portal/invoices", [id, "pdf"]);
}
