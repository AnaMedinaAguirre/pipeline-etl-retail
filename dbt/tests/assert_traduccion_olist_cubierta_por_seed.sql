-- Toda categoría de la tabla de traducción publicada por Olist debe existir en el
-- seed categorias_es (además, stg_olist__products verifica las categorías usadas).
select t.product_category_name
from {{ source('raw', 'olist_category_translation') }} t
left join {{ ref('categorias_es') }} s
  on s.categoria_pt = lower(trim(t.product_category_name))
where s.categoria_pt is null
