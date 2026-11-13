INSERT INTO "company_subscriptions" (
    "id", "company_id", "plan_id", "status", "activation_date", "created_at", "updated_at"
)
SELECT
    gen_random_uuid(), c."id", p."id", 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM "companies" c
JOIN LATERAL (
    SELECT candidate."id"
    FROM "subscription_plans" candidate
    WHERE UPPER(candidate."name") = UPPER(c."subscription_plan")
       OR candidate."code" = UPPER(c."subscription_plan")
    ORDER BY CASE WHEN UPPER(candidate."name") = UPPER(c."subscription_plan") THEN 0 ELSE 1 END
    LIMIT 1
) p ON TRUE
LEFT JOIN "company_subscriptions" existing ON existing."company_id" = c."id"
WHERE existing."company_id" IS NULL;
