-- Productos tipados. Se corrigen las erratas de origen ("lenght" -> longitud)
-- y los productos sin categoría se marcan como 'sin_categoria'.
select
    product_id,
    coalesce(nullif(lower(trim(product_category_name)), ''), 'sin_categoria') as categoria_pt,
    product_name_lenght::integer            as largo_nombre,
    product_description_lenght::integer     as largo_descripcion,
    product_photos_qty::integer             as cantidad_fotos,
    {{ a_numero('product_weight_g') }}      as peso_g,
    {{ a_numero('product_length_cm') }}     as largo_cm,
    {{ a_numero('product_height_cm') }}     as alto_cm,
    {{ a_numero('product_width_cm') }}      as ancho_cm
from {{ source('raw', 'olist_products') }}
