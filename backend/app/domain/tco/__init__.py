"""TCO domain package — pure calculator over snapshots fetched by repositories.

Public surface:

* ``inputs``    — DTO bundles passed by service layer
* ``snapshots`` — read-only views of reference tables (catalog, pricing, …)
* ``result``    — DTO returned by the calculator
* ``calculator`` — facade orchestrating components
* ``components`` — one module per TCO line item
"""
