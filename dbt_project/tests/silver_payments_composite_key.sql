-- Null key components and duplicate pairs both fail this data contract.
select order_id, payment_sequential, count(*) as occurrences
from {{ ref('silver_payments') }}
group by order_id, payment_sequential
having count(*) > 1 or order_id is null or payment_sequential is null
