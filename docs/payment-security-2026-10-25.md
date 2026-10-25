# Payment namespace and allocation changes, 2026-10-25

Exact-amount invoices previously used overlapping micro-USDC suffixes. In
particular, hashing a desk ID into ten buckets assigned both Plinth and Tideline
to bucket 8; Emberline used the entire legacy 1–9999 range.

New quotes use explicit, disjoint suffixes above the old range:

| Desk | Raw-unit suffix, inclusive |
| --- | --- |
| Solrecord | 10001–10999 |
| Smokeproof | 11001–11999 |
| Seamark | 12001–12999 |
| Plinth | 13001–13999 |
| Tideline | 14001–14999 |
| Emberline | 15001–15999 |

The six desks' plan bases are whole USDC amounts. These ranges distinguish those
plans across the six desks; they are not a global payment namespace for arbitrary
fractional prices in other ecosystem products. Services sharing a recipient with
other payment rails need separate recipient or transfer-claim coordination.

The quote allocator reserves and commits an amount in one database critical
section: PostgreSQL transaction advisory lock, SQLite `BEGIN IMMEDIATE`, and a
process lock for shared in-memory connections. Threads and independent worker
processes are covered by regression tests.

Existing invoice amounts and payment status are preserved. Previously paid
invoices retain access. An unpaid invoice outside its desk's new namespace is
flagged `manual_reconciliation_needed`, stops offering a wallet link, and cannot
automatically mint access through polling, confirmation, simulation or direct
settlement. A legacy transfer therefore cannot credit both desks. Payment pages
tell its buyer to retain the invoice and transaction hash and not pay again.
The authenticated operator must verify and resolve that old quote using the
protected manual grant workflow; no public endpoint bypasses reconciliation.

Emberline polling also verifies transfer time against invoice creation/grace,
matching its confirmation path. Transaction reuse is rejected before minting.
The native transfer payload and wallet-signature format do not change.
