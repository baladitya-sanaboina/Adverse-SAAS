-- The Admin can take a task too (owner request 2026-11-28); such tasks have no commission.
ALTER TYPE "TaskAssigneeType" ADD VALUE IF NOT EXISTS 'ADMIN';
