-- Productos con categoría en portugués, inglés (corregido) y español, y su grupo.
select
    {{ dbt_utils.generate_surrogate_key(['p.product_id']) }} as producto_key,
    p.product_id,
    p.categoria_pt,
    c.categoria_en,
    c.categoria_es,
    c.grupo                as grupo_categoria,
    p.peso_g,
    p.largo_cm,
    p.alto_cm,
    p.ancho_cm,
    p.cantidad_fotos
from {{ ref('stg_olist__products') }} p
left join {{ ref('categorias_es') }} c on c.categoria_pt = p.categoria_pt
