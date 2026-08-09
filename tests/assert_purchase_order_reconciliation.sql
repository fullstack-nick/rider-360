select * from {{ ref('audit_reconciliation') }}
where purchases_without_orders != 0 or orders_without_purchases != 0
