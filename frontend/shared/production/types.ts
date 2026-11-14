// Shapes returned by the production-management backend (backend/app/schemas/production.py).
// Money values arrive as decimal strings, dates as ISO strings.

export type TaskStatus =
  | "PENDING"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "SUBMITTED"
  | "REVIEW"
  | "APPROVED"
  | "COMPLETED"
  | "CANCELLED";
export type TaskPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export type AssigneeRole = "MANAGER" | "EMPLOYEE";
export type FileKind = "REFERENCE" | "DELIVERABLE";
export type PaymentMethod = "CASH" | "BANK_TRANSFER" | "UPI" | "CHEQUE" | "CARD" | "OTHER";
export type BudgetEntryType = "INITIAL" | "TOP_UP" | "ADJUSTMENT";
export type ReportPeriod = "all" | "today" | "this_week" | "this_month" | "previous_month" | "custom";

export type NamedRef = { id: string; name: string; code: string };
export type PersonRef = { id: string; name: string; role: AssigneeRole };
export type Paged<T> = { items: T[]; page: number; page_size: number; total: number; total_pages: number };

export type AdminTask = {
  id: string;
  code: string;
  title: string;
  description: string;
  priority: TaskPriority;
  status: TaskStatus;
  client: NamedRef;
  service: NamedRef;
  assignee: PersonRef | null;
  monitor: NamedRef | null;
  due_date: string | null;
  is_overdue: boolean;
  billable: boolean;
  currency: string;
  client_pricing_model: string;
  client_price_default: string | null;
  client_price: string;
  client_price_reason: string;
  commission_default: string | null;
  commission: string | null;
  commission_reason: string;
  margin: string;
  allowed_statuses: TaskStatus[];
  files_count: number;
  comments_count: number;
  created_by_name: string;
  created_at: string;
  updated_at: string;
  assigned_at: string | null;
  started_at: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
};

export type StatusHistory = {
  id: string;
  from_status: TaskStatus | null;
  to_status: TaskStatus;
  note: string;
  actor_name: string;
  created_at: string;
};
export type PriceChange = {
  id: string;
  field: "CLIENT_PRICE" | "COMMISSION";
  old_amount: string | null;
  new_amount: string | null;
  reason: string;
  actor_name: string;
  created_at: string;
};
export type TaskComment = { id: string; author_id: string; author_name: string; content: string; created_at: string };
export type TaskFile = {
  id: string;
  kind: FileKind;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  uploaded_by_name: string;
  created_at: string;
};

export type AdminTaskDetail = AdminTask & {
  status_history: StatusHistory[];
  price_changes: PriceChange[];
  comments: TaskComment[];
  files: TaskFile[];
};

export type BudgetCheck = {
  has_budget: boolean;
  currency: string;
  total: string;
  used: string;
  committed: string;
  remaining: string;
  overage: string;
  projected_used: string;
  projected_overage: string;
  exceeds_with_new_task: boolean;
  message: string;
};

export type TaskWrite = { task: AdminTaskDetail; budget: BudgetCheck };

export type PricingPreview = {
  client: NamedRef;
  service: NamedRef;
  client_pricing_model: string;
  client_price_default: string | null;
  assignee: PersonRef | null;
  commission_default: string | null;
  currency: string;
  budget: BudgetCheck;
};

export type AssigneeOption = { id: string; name: string; role: AssigneeRole; code: string; email: string };

export type ServiceCount = {
  service_id: string;
  service_name: string;
  completed: number;
  in_progress: number;
  charged: string;
};

export type BudgetEntry = {
  id: string;
  type: BudgetEntryType;
  amount: string;
  currency: string;
  note: string;
  created_by_name: string;
  created_at: string;
};
export type ClientBudget = { client: NamedRef; budget: BudgetCheck; entries: BudgetEntry[] };

export type ClientPayment = {
  id: string;
  client: NamedRef;
  amount: string;
  currency: string;
  received_on: string;
  method: PaymentMethod;
  reference: string;
  note: string;
  created_by_name: string;
  created_at: string;
};
export type SalaryPayment = {
  id: string;
  user_id: string;
  employee_name: string;
  period_month: string;
  amount: string;
  currency: string;
  paid_on: string;
  method: PaymentMethod;
  reference: string;
  note: string;
  created_by_name: string;
  created_at: string;
};
export type ManagerPayout = {
  id: string;
  manager_user_id: string;
  manager_name: string;
  amount: string;
  currency: string;
  paid_on: string;
  method: PaymentMethod;
  reference: string;
  note: string;
  created_by_name: string;
  created_at: string;
};
export type PaymentList<T> = Paged<T> & { total_amount: string };

export type SalaryRecord = {
  id: string;
  monthly_amount: string;
  currency: string;
  effective_from: string;
  effective_to: string | null;
  note: string;
  created_by_name: string;
  created_at: string;
};
export type CommissionLine = {
  task_id: string;
  code: string;
  title: string;
  service_name: string;
  status: TaskStatus;
  commission: string;
  approved_at: string | null;
};
export type WalletPeriod = {
  index: number;
  start: string;
  end: string | null;
  topped_up: string;
  earned: string;
  balance: string;
  items: number;
};
export type WalletLine = { day: string; kind: "TOP_UP" | "COMMISSION"; title: string; amount: string; balance: string };
/** Manager advance (Phase 12): top-ups minus commission earned. */
export type ManagerWallet = {
  topped_up: string;
  earned: string;
  balance: string;
  periods: WalletPeriod[];
  lines: WalletLine[];
};
export type ManagerEarnings = {
  currency: string;
  earned: string;
  upcoming: string;
  paid: string;
  pending: string;
  current_month_earned: string;
  tasks: CommissionLine[];
  payouts: ManagerPayout[];
  wallet?: ManagerWallet | null;
};
export type SalaryMonth = { month: string; due: string; paid: string; pending: string };
export type EmployeeSalary = {
  currency: string;
  current_monthly_salary: string | null;
  total_due: string;
  total_paid: string;
  pending: string;
  months: SalaryMonth[];
  payments: SalaryPayment[];
};
export type PersonFinance = {
  person: PersonRef;
  manager: ManagerEarnings | null;
  employee: EmployeeSalary | null;
  salary_history: SalaryRecord[];
};

export type PeriodInfo = { period: ReportPeriod; start: string | null; end: string | null };
export type FinanceSummary = {
  period: PeriodInfo;
  currency: string;
  revenue: string;
  commission_cost: string;
  salary_cost: string;
  team_cost: string;
  gross_margin: string;
  approved_items: number;
  pending_client_payments: string;
  pending_manager_payments: string;
  pending_salary_payments: string;
  pending_team_payments: string;
  open_tasks: number;
  unassigned_tasks: number;
  in_review_tasks: number;
  overdue_tasks: number;
  top_client: NamedRef | null;
  top_client_open_tasks: number;
};
export type ClientReportRow = {
  client: NamedRef;
  total_tasks: number;
  completed_tasks: number;
  open_tasks: number;
  billed: string;
  received: string;
  pending: string;
  budget_total: string;
  budget_remaining: string;
  services: ServiceCount[];
};
export type TeamReportRow = {
  person: PersonRef;
  total_tasks: number;
  completed_tasks: number;
  open_tasks: number;
  earnings: string;
  paid: string;
  pending: string;
};
export type ServiceReportRow = {
  service: NamedRef;
  items: number;
  revenue: string;
  commission_cost: string;
  margin: string;
};
export type Report<T> = { period: PeriodInfo; currency: string; rows: T[] };
export type ServiceReport = Report<ServiceReportRow> & { totals: ServiceReportRow | null };
