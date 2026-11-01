---
name: draft-invoice
description: Draft a Kedeka invoice or quote from a client and line items, change a draft, or turn an existing quote into an invoice. Use when the user asks to create, prepare, edit, or bill something (e.g. "buatkan invoice untuk PT Kopi Senja", "bikin penawaran desain logo", "tambahkan catatan di draft invoice", "jadikan penawaran ini invoice", "invoice Rani for 1 branding package").
---

# Draft an invoice or quote

The result is always a draft. Nothing is published or sent to the client by this workflow.

Explicit user instructions take priority over this skill. Reply in the user's language.

## Inputs to collect

- Document type: invoice or quote. If the user does not say, assume invoice and mention it in the summary.
- Client (required).
- Line items: product or description, quantity, unit price.
- Optional: project, issue date, due date, currency, notes, discount.

Never invent a client, a price, a tax rate, or a due date. Missing values that Kedeka fills from workspace settings (number, due date, sender, bank account) can stay empty.

## Steps

1. **Client.** `search_records` with `entity: client` and `filters: {"query": "<name>"}`.
   - One clear match: use its ID.
   - `selection.required=true` or several similar names: show the candidates with their distinguishing details and ask the user to pick.
   - No match: say so and ask whether to create the client (see the manage-records skill) or use another name.
2. **Items.** For each item that sounds like a product or service, `search_records` with `entity: catalog_item`.
   - A catalog match: use its `product_id` so name, unit, price, and tax come from the catalog. Use the user's price only if they gave one explicitly.
   - No match: a free-text line with `description`, `quantity`, `unit`, and `unit_price` from the user. If the price is missing, ask for it.
   - If the user mentions a tax, call `get_report` with `report: workspace_reference` and use a matching `tax_rate_id`. Do not guess tax rates.
3. **Project (optional).** `search_records` with `entity: project`.
4. **Confirm.** Show a compact summary: type, client, each line (name, qty × price), any tax or discount, and the currency. Ask the user to confirm or correct it.
5. **Create.** After confirmation, call `create_record` once:

   ```json
   {"entity": "document", "idempotency_key": "<uuid>", "data": {
     "document_type": "invoice", "customer_id": "<client id>", "due_date": "YYYY-MM-DD",
     "items": [{"description": "Konsultasi branding", "quantity": 2, "unit": "jam", "unit_price": 500000}]
   }}
   ```

   Other `data` fields: `project_id`, `heading`, `issue_date`, `currency` (IDR, USD, SGD, EUR), `notes`. Item fields: `product_id`, `description`, `quantity`, `unit`, `unit_price`, `tax_rate_id`, `discount_percent`.
6. **Report.** Give the document number, client, total, and the review link from `links.edit`. Say it is a draft that the user can check, publish, and send from Kedeka.

## Change a draft

1. Find it with `search_records` (`entity: document`, `filters: {"document_type": "invoice", "status": "draft", "customer_id": "<id>"}`), then read it with `get_record` (`entity: document`, `id`, `options: {"document_type": "invoice"}`) to get its `revision`.
2. Confirm the change, then `update_record` with `entity: document`, the `id`, and `data` holding `expected_revision` (the revision you read) plus only the changed fields. Sending `items` replaces all lines, so include the lines to keep.
3. If the result is `CONFLICT`, read the document again and show the user what changed before retrying.

## Quote to invoice

1. Find the quote with `search_records` (`entity: document`, `filters: {"document_type": "quote"}`). Ask the user to pick if more than one fits.
2. Confirm which quote will be converted.
3. Call `create_record` with `entity: invoice_from_quote`, a new `idempotency_key`, and `data: {"document_id": "<quote id>"}`. This creates a draft invoice and marks the source quote as converted. Report the draft and its link.

## After the draft

- Publish only when the user explicitly asks, and only through `publish_document` with the revision the user saw. If publishing is disabled, say so.
- To email the client, the document must be published first. Then call `create_secure_link` with `action: send_document_email` and the document ID. You may suggest `prefill.message` in the user's language. Share the link: the user checks the recipient and message in Kedeka and presses Send there. When they say they are done, confirm with `get_secure_link_status`.
- If the user wants the client's tax ID (NPWP/NITKU) on the invoice, never ask them to type it in the chat. Call `create_secure_link` with `action: client_details` and the client ID, and share the link.
