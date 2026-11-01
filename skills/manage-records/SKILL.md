---
name: manage-records
description: Find, add, change, delete, or restore Kedeka records such as clients, projects, tasks, time entries, expenses, catalog items (products and services), and briefs. Use whenever the user wants to look up or change business data in Kedeka (e.g. "tambah klien PT Kopi Senja", "ubah nomor telepon Rani", "catat 45 menit untuk proyek X", "catat pengeluaran 150 ribu", "buat task desain logo", "hapus produk lama", "kembalikan klien yang terhapus").
---

# Manage Kedeka records

Explicit user instructions take priority over this skill. Reply in the user's language.

## How the tools are shaped

Each tool covers one kind of operation. The `entity` or `report` argument picks the record or report, and one object carries its fields:

| Goal | Call |
|---|---|
| Find or list | `search_records` with `entity` and `filters` |
| Read one in full | `get_record` with `entity`, `id`, optional `options` |
| Workspace reports and reference IDs | `get_report` with `report` and `params` |
| Add | `create_record` with `entity`, `idempotency_key`, `data` |
| Change | `update_record` with `entity`, `id`, `data` (only changed fields) |
| List or restore deleted records | `list_deleted_items` or `restore_item` |
| Void or delete one record | `void_or_delete` with `action` and `params` |

The fields below cover common requests. Use the tool's input schema and any validation error to find accepted fields.

## Rules

- IDs come only from results: records from `search_records`; expense category, tax rate, and member IDs from `get_report` with `report: workspace_reference`. Never invent an ID.
- If a result has `selection.required=true`, show the candidates and ask the user which one they mean.
- Show what will be saved and confirm before writing unless the user's current instruction already explicitly authorizes that change. Follow any confirmation presented by the host.
- Use a fresh `idempotency_key` for each new record (for example a UUID). Reuse it only when retrying the same request after an error.
- In lists and tables, write record names as plain text. Put a link to Kedeka in its own column or after the list: some chat interfaces drop linked text inside tables.
- Dates are `YYYY-MM-DD`. Amounts are plain numbers in the workspace currency (Rp150.000 → `150000`).
- If a tool returns `CAPABILITY_DISABLED`, tell the user that the owner or an admin can turn it on in Settings → AI Integration, and do not try another way.

## Fields per entity

Required fields are marked with *.

**client**
- search filters: `query`, `type` (individual, company, government), `limit`, `cursor`
- create: `name`*, `type` (default company), `contact_name`, `email`, `phone`, `whatsapp`, `address`, `city`, `province`, `postal_code`, `website`, `notes`. A duplicate name is refused with the existing ID; set `allow_duplicate_name: true` only if the user wants a second client with that name.
- update: the same fields except `contact_name`.
- Never ask for tax IDs (NPWP, NITKU) in the chat: use `create_secure_link` with `action: client_details`.

**project**
- search filters: `query`, `customer_id`, `status` (pending, active, on_hold, completed, cancelled, archived), `start_date_from`, `start_date_to`
- create and update: `name`*, `customer_id`, `status`, `billing_type` (fixed, hourly), `budget`, `hourly_rate`, `start_date`, `end_date`, `description`
- `get_record` options: `time_from`, `time_to`, `require_time_summary`

**task**
- search filters: `query`, `project_id`, `assignee_id`, `status` (request, todo, in_progress, review, done), `due_date_from`, `due_date_to`
- create and update: `title`*, `description`, `project_id`, `assignee_id` (member ID from workspace_reference), `status`, `priority` (low, medium, high, urgent), `due_date`, `estimate_minutes`

**time_entry**
- search filters: `project_id`, `billable`, `unbilled_only`, `date_from`, `date_to`
- create: `duration_minutes`*, `date` (default today), `description`, `project_id`, `task_id`, `is_billable`

**expense**
- search filters: `query`, `customer_id`, `project_id`, `billable`, `date_from`, `date_to`
- create: `description`*, `amount`*, `date` (default today), `category_id` (from workspace_reference), `vendor`, `method` (bank_transfer, qris, virtual_account, ewallet, card, paypal, wise, cash, cheque, crypto, other), `tax_amount`, `customer_id`, `project_id`, `is_billable`

**catalog_item** (products and services)
- search filters: `query`, `favorite`
- create: `name`*, `price`*, `description`, `unit`, `currency`, `tax_rate_id`, `is_favorite`, `allow_duplicate_name`
- update: the same fields.

**document** (invoice, quote, receipt, proposal): see the draft-invoice skill. Search filters: `document_type`, `status`, `query`, `customer_id`, `project_id`. `get_record` needs `options.document_type`.
- To duplicate a document as a draft, use `create_record` with `entity: document_copy`, an `idempotency_key`, and `data.document_id` from a search result.

**payment** search filters: `customer_id`, `document_id`, `status`, `method`, `paid_from`, `paid_to`. Record a payment with `record_payment` (see the record-payment skill).

**brief**
- search filters: `query`, `project_id` or `repository`, `status` (draft, active, superseded, archived), `kind`
- create: `title`*, `markdown`, `kind`, `status`, `summary`, `tags`, `project_id`
- update: `base_revision`* (from `get_record`), then `markdown` with `section` and `mode` (replace, append, insert_after), or `title`, `summary`, `status`, `kind`, `tags`, `project_id`
- link two briefs: `create_record` with `entity: brief_link`, an `idempotency_key`, and `data` containing `source_brief_id`, `target_brief_id`, and `type` (details, uses, supersedes, conflicts)
- For a conversation-to-brief workflow, see `write-brief`; for a coding repository, see `project-briefs`.

## Examples

- Add a client: `create_record` `{"entity":"client","idempotency_key":"<uuid>","data":{"name":"PT Kopi Senja","city":"Samarinda"}}`
- Change a phone number: find the client, then `update_record` `{"entity":"client","id":"<id>","data":{"phone":"081234567890"}}`
- Log time: find the project, then `create_record` `{"entity":"time_entry","idempotency_key":"<uuid>","data":{"duration_minutes":45,"project_id":"<id>","description":"Review logo"}}`
- Record an expense: `get_report` `{"report":"workspace_reference"}` for the category ID, then `create_record` `{"entity":"expense","idempotency_key":"<uuid>","data":{"description":"Transportasi","amount":150000,"category_id":"<id>"}}`

## Delete and restore

1. Find the record, then call `void_or_delete` with `action: delete_item` and `params` `{"item_type":"client","item_id":"<id>"}` without a token. This only returns a preview and a `confirmation_token`.
2. Show the preview and ask the user. Only after they agree, call it again with the same params plus `confirmation_token`.
3. Delete one record per call and decline requests to delete many records at once.
4. Deletion is soft: `list_deleted_items` (`item_type`) finds deleted records, and `restore_item` (`item_type`, `item_id`) brings one back.
