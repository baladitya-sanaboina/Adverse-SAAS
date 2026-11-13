export type LeadSource = "WEBSITE" | "REFERRAL" | "EMAIL" | "PHONE" | "SOCIAL" | "OTHER";
export type LeadStatus = "NEW" | "CONTACTED" | "QUALIFIED" | "LOST" | "CONVERTED";
export type OpportunityStage = "NEW" | "QUALIFIED" | "PROPOSAL" | "NEGOTIATION" | "WON" | "LOST";
export type OpportunityStatus = "OPEN" | "CLOSED";

export type CrmOption = { id: string; name: string };
export type CrmOptions = { owners: CrmOption[]; clients: CrmOption[] };

export type Lead = {
  id: string;
  company_id: string;
  client_id: string | null;
  owner_id: string;
  owner_name: string;
  name: string;
  company_name: string;
  email: string | null;
  phone: string | null;
  source: LeadSource;
  status: LeadStatus;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type Opportunity = {
  id: string;
  company_id: string;
  client_id: string;
  client_name: string;
  lead_id: string | null;
  owner_id: string;
  owner_name: string;
  name: string;
  description: string;
  value: string;
  currency: string;
  stage: OpportunityStage;
  status: OpportunityStatus;
  expected_close_date: string | null;
  created_at: string;
  updated_at: string;
};

export type Paged<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type CrmInitialEntity = { type: "lead"; id: string } | { type: "opportunity"; id: string };
