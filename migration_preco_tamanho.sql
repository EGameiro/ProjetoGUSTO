-- Migration: preços por tamanho no cardápio
ALTER TABLE cardapio_web
    ADD COLUMN preco_mini      DECIMAL(10,2) NULL AFTER preco,
    ADD COLUMN preco_normal    DECIMAL(10,2) NULL AFTER preco_mini,
    ADD COLUMN preco_executiva DECIMAL(10,2) NULL AFTER preco_normal;

-- Migrar valor existente para todos os tamanhos (pode ajustar depois pelo portal)
UPDATE cardapio_web SET
    preco_mini      = preco,
    preco_normal    = preco,
    preco_executiva = preco
WHERE preco IS NOT NULL AND tipo = 'prato';
