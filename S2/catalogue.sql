BEGIN;

-- 1. RÉCEPTION BRUTE
CREATE TEMP TABLE rec_categories (
    category_id integer,
    category_name text,
    parent_category_id integer
);

CREATE TEMP TABLE rec_products (
    product_id integer,
    sku text,
    product_name text,
    category_id integer,
    first_listed_on date
);

\copy rec_categories FROM '/tmp/novamarket-s2/categories.csv' WITH (FORMAT csv, HEADER true)
\copy rec_products FROM '/tmp/novamarket-s2/products.csv' WITH (FORMAT csv, HEADER true)

-- 2. SCHÉMA DU CATALOGUE
CREATE TABLE categories (
    category_id integer PRIMARY KEY,
    category_name text NOT NULL,
    parent_category_id integer REFERENCES categories(category_id)
);

CREATE TABLE products (
    product_id integer PRIMARY KEY,
    sku text NOT NULL UNIQUE,
    product_name text NOT NULL,
    category_id integer NOT NULL REFERENCES categories(category_id),
    first_listed_on date NOT NULL
);

-- 3. INTÉGRATION (Catégories d'abord, puis produits dédoublonnés)
INSERT INTO categories (category_id, category_name, parent_category_id)
SELECT DISTINCT category_id, category_name, parent_category_id
FROM rec_categories
ORDER BY parent_category_id NULLS FIRST, category_id;

INSERT INTO products (product_id, sku, product_name, category_id, first_listed_on)
SELECT DISTINCT product_id, sku, product_name, category_id, first_listed_on
FROM rec_products;

-- 4. LIAISON AVEC LES LIGNES DE COMMANDES S1 (Couverture 100% vérifiée)
ALTER TABLE order_items
    ADD CONSTRAINT order_items_product_id_fkey
    FOREIGN KEY (product_id) REFERENCES products(product_id);

COMMIT;