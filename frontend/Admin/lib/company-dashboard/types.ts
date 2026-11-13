export interface CompanyDashboard {
  company: { id: string; name: string; logo_url: string | null };
  current_user: { id: string; name: string; role: "COMPANY_ADMIN" };
  statistics: {
    employees: number;
    clients: number;
    projects: number;
    active_projects: number | null;
    completed_projects: number | null;
    finance_total: string | null;
  };
  recent_activity: {
    action: string;
    subject: string;
    description: string;
    occurred_at: string;
  }[];
  quick_actions: { label: string; href: string; module: string; action: string }[];
}

export interface CompanyDashboardError {
  detail?: string;
}
