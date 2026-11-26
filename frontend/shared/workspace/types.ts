// Shapes of the /workspace API (Manager and Employee). These contain no client prices or margin.
import type {
  ManagerPayout,
  SalaryPayment,
  StatusHistory,
  TaskComment,
  TaskFile,
  TaskPriority,
  TaskStatus,
} from "../production/types";

export type WorkerTask = {
  id: string;
  code: string;
  title: string;
  description: string;
  priority: TaskPriority;
  status: TaskStatus;
  client_name: string;
  service_name: string;
  // CLIENT_WRITE / CLIENT_READ: seen through access to the task's client (owner request 2026-11-26).
  my_role: "ASSIGNEE" | "MONITOR" | "CLIENT_WRITE" | "CLIENT_READ";
  can_comment: boolean;
  assignee_name: string | null;
  due_date: string | null;
  is_overdue: boolean;
  my_commission: string | null;
  currency: string;
  allowed_statuses: TaskStatus[];
  can_upload_deliverables: boolean;
  files_count: number;
  comments_count: number;
  created_at: string;
  assigned_at: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  completed_at: string | null;
};

export type WorkerTaskDetail = WorkerTask & {
  status_history: StatusHistory[];
  comments: TaskComment[];
  files: TaskFile[];
};

export type WorkspaceDashboard = {
  role: "MANAGER" | "EMPLOYEE";
  counts: {
    assigned: number;
    in_progress: number;
    submitted: number;
    in_review: number;
    approved: number;
    completed: number;
    overdue: number;
    monitoring: number;
  };
  currency: string;
  current_month_earnings: string;
  pending_payment: string;
  upcoming_tasks: WorkerTask[];
};

export type { ManagerPayout, SalaryPayment };
