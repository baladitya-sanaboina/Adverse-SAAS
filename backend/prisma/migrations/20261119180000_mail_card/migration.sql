-- A mail can carry a "card" (title, detail rows, an item table, a button label) so app mails
-- read like proper mails in the internal mailbox (owner request 2026-11-19). Plain body stays.
ALTER TABLE "mail_messages" ADD COLUMN "card" JSONB;
