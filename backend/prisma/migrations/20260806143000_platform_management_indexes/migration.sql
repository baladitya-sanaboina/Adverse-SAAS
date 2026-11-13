CREATE INDEX "companies_status_created_at_idx" ON "companies"("status", "created_at");
CREATE INDEX "companies_subscription_plan_status_idx" ON "companies"("subscription_plan", "status");
CREATE INDEX "subscription_plans_status_display_order_idx" ON "subscription_plans"("status", "display_order");
CREATE INDEX "users_role_id_status_created_at_idx" ON "users"("role_id", "status", "created_at");
