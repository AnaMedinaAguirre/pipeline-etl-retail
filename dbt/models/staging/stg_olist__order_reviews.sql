-- Reseñas tipadas y sin duplicados exactos.
-- En Olist un mismo review_id puede aparecer en varios pedidos, por eso la clave
-- única de este modelo es (review_id, order_id).
with tipado as (
    select
        review_id,
        order_id,
        review_score::integer                       as nota,
        nullif(trim(review_comment_title), '')      as titulo_comentario,
        nullif(trim(review_comment_message), '')    as comentario,
        review_creation_date::timestamp             as fecha_hora_creacion,
        review_answer_timestamp::timestamp          as fecha_hora_respuesta,
        row_number() over (
            partition by review_id, order_id
            order by review_answer_timestamp desc nulls last
        ) as n
    from {{ source('raw', 'olist_order_reviews') }}
)

select
    review_id,
    order_id,
    nota,
    titulo_comentario,
    comentario,
    fecha_hora_creacion,
    fecha_hora_respuesta
from tipado
where n = 1
