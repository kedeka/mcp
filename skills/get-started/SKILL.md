---
name: get-started
description: Introduce the Kedeka plugin right after it is installed, or when the user asks what Kedeka can do, which workspace is connected, or which permissions are on (e.g. "Kedeka bisa apa saja?", "workspace mana yang terhubung?", "what can you do with Kedeka?").
---

# Get started with Kedeka

Kedeka is the user's business admin: invoices, quotes, receipts, clients, products, projects, tasks, time, expenses, briefs, and financial reports for one connected workspace.

Explicit user instructions take priority over this skill. Reply in the user's language.

## Steps

1. Call `get_report` with `report: business_context` once. It returns the workspace label, time zone, currency, and the capabilities this connection holds.
2. Give a short welcome (no more than about 8 lines):
   - Name the connected workspace and its default currency.
   - Group what the connection can do into "view" and "manage", using only the capabilities returned. Do not promise anything the result does not list.
   - If manage (write) capabilities are missing, say the owner or an admin can turn them on in Settings → AI Integration in Kedeka.
   - Mention that sensitive data such as tax IDs and bank account numbers is entered on a secure Kedeka page, never in the chat.
3. Offer three example requests that fit the returned capabilities, such as:
   - "Which invoices are unpaid and overdue?"
   - "Draft an invoice for <client>: <item>, <price>."
   - "How much revenue and profit did I make this month?"
   Write the examples in the user's language.

## Do not

- Do not call other tools or list data before the user asks for something.
- If the call fails with an authorization error, ask the user to reconnect Kedeka instead of guessing what is available.
