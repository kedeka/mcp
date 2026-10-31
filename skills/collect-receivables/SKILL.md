---
name: collect-receivables
description: Review unpaid and overdue Kedeka invoices, decide who to follow up first, and draft payment reminder messages for the user to send. Use when the user asks who has not paid, how much is outstanding, or for help chasing payments (e.g. "siapa yang belum bayar?", "bantu tagih klien yang telat", "draft a WhatsApp reminder for overdue invoices").
---

# Collect receivables

This workflow reads data and writes message drafts. It never sends anything: the user sends the reminders themselves.

Explicit user instructions take priority over this skill. Reply in the user's language.

## Steps

1. **Read receivables.** Call `get_receivables`.
   - For one client, find the client with `search_clients` first and pass `customer_id`.
   - For "overdue" or "telat", pass `overdue_only: true`.
   - The tool is for workspace owners and admins. If it is refused, say so plainly.
2. **Summarize.** Show:
   - Total outstanding and the totals per age bucket (not yet due, 0–30, 31–60, 61–90, over 90 days).
   - A short table of the oldest unpaid invoices: number, client, due date, days overdue, balance.
   Use the currency returned by the tool, formatted for the user's locale.
3. **Prioritize.** Suggest an order to follow up: longest overdue first, then the largest balances. Keep it to the top five unless the user asks for more.
4. **Draft reminders (on request).** For each invoice the user picks, call `get_document` if you need its details, then write a short reminder:
   - Polite and specific: invoice number, amount due, original due date.
   - Firmer tone only for invoices more than 30 days overdue, and never threatening.
   - Use the client's name from the data. Do not add bank details, penalties, or deadlines that are not in the data.
   - Format for the channel the user names (WhatsApp: short, no subject line; email: subject plus body).
   - Include the document's public link only if the tool result provides one.

## Do not

- Do not claim a reminder was sent. The user sends WhatsApp and email reminders themselves.
- If the user wants to email the invoice itself to the client, call `create_secure_link` with `action: send_document_email` and the invoice ID, with your reminder as `prefill.message`. The email goes out only after the user presses Send in Kedeka.
- Do not record payments or change invoices in this workflow. If the user says a client already paid, switch to recording the payment and confirm it first.
