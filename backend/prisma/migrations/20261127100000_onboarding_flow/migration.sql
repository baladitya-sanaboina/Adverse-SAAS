-- One onboarding flow for clients, employees and managers (owner request 2026-11-27): the
-- onboarding packet now belongs to the person's invitation (they set their password on the same
-- page), and the files they upload there (ID proof, photo) are listed on the packet.
ALTER TABLE "onboarding_packets" ADD COLUMN "invitation_id" UUID;
ALTER TABLE "onboarding_packets" ADD COLUMN "uploads" JSONB NOT NULL DEFAULT '{}';
CREATE INDEX "onboarding_packets_invitation_id_idx" ON "onboarding_packets"("invitation_id");
ALTER TABLE "onboarding_packets" ADD CONSTRAINT "onboarding_packets_invitation_id_fkey"
  FOREIGN KEY ("invitation_id") REFERENCES "company_invitations"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- Removing an employee or manager who already has work (owner decision 2026-11-27): they can no
-- longer sign in and leave every list, but their past tasks and payments keep their name.
ALTER TABLE "employees" ADD COLUMN "removed_at" TIMESTAMP(3);
