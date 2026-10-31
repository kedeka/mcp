---
name: draft-invoice
description: Draft a Kedeka invoice or quote from a client and line items, or turn an existing quote into an invoice. Use when the user asks to create, prepare, or bill something (e.g. "buatkan invoice untuk PT Kopi Senja", "bikin penawaran desain logo", "jadikan penawaran ini invoice", "invoice Rani for 1 branding package").
---

# Draft an invoice or quote

The result is always a draft. Nothing is published or sent to the client by this workflow.

Explicit user instructions take priority over this skill. Reply in the user's language.

## Inputs to collect

- Document type: invoice or quote. If the user does not say, assume invoice and mention it in the summary.
- Client (required).
- Line items: product or description, quantity, unit price.
- Optional: project, issue date, due date, currency, notes, discount.

Never invent a client, a price, a tax rate, or a due date. Missing values that the tool fills from workspace settings (number, due date, sender, bank account) can stay empty.

## Steps

1. **Client.** Call `search_clients` with the client name.
   - One clear match: use its ID.
   - `selection.required=true` or several similar names: show the candidates with their distinguishing details and ask the user to pick.
   - No match: say so and ask whether to create the client with `create_client` (only if the connection can manage clients) or to use another name.
2. **Items.** For each item that sounds like a product or service, call `search_catalog_items`.
   - A catalog match: use its `product_id` so name, unit, price, and tax come from the catalog. Use the user's price only if they gave one explicitly.
   - No match: use a free-text line with `description`, `quantity`, `unit`, and `unit_price` from the user. If the price is missing, ask for it.
   - If the user mentions a tax, call `get_workspace_reference` and use a matching `tax_rate_id`. Do not guess tax rates.
3. **Project (optional).** If the user names a project, find it with `search_projects`.
4. **Confirm.** Show a compact summary: type, client, each line (name, qty × price), any tax or discount, and the currency. Ask the user to confirm or correct it.
5. **Create.** After confirmation, call `create_document_draft` once with a fresh `idempotency_key`. Reuse the same key only when retrying the same request after an error.
6. **Report.** Give the client, the total, and the review link from `links.edit`. Say it is a draft that the user can check, publish, and send from Kedeka.

## Quote to invoice

When the user wants to turn a quote into an invoice:

1. Find the quote with `search_documents` (`document_type: quote`). Ask the user to pick if more than one fits.
2. Confirm which quote will be converted.
3. Call `convert_quote_to_invoice` with a fresh `idempotency_key`, then report the new draft invoice and its link.

## After the draft

- To change the draft, use `update_document_draft`; confirm the changes first.
- Publish only when the user explicitly asks, and only through `publish_document` with the revision the user saw. If publishing is disabled, say so.
- To email the client, the document must be published first. Then call `create_secure_link` with `action: send_document_email` and the document ID. You may suggest `prefill.message` in the user's language. Share the link: the user checks the recipient and message in Kedeka and presses Send there. When they say they are done, confirm with `get_secure_link_status`.
- If the user wants the client's tax ID (NPWP/NITKU) on the invoice, never ask them to type it in the chat. Call `create_secure_link` with `action: client_details` and the client ID, and share the link.
