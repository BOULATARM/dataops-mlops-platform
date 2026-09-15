-- Null key components and duplicate pairs both fail this data contract.
select order_id, order_item_id, count(*) as occurrences
from {{ ref('silver_order_items') }}
group by order_id, order_item_id
having count(*) > 1 or order_id is null or order_item_id is null
