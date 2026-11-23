BEGIN;

-- ==========================================
-- 1. RÉCEPTION BRUTE (Tables Temporaires)
-- ==========================================
CREATE TEMP TABLE reception_customers (customer_id integer, customer_name text, city text);
CREATE TEMP TABLE reception_orders (order_id integer, customer_id integer, ordered_on date, status text);
CREATE TEMP TABLE reception_order_items (order_item_id integer, order_id integer, product_id integer, quantity integer, unit_price_cents integer);
CREATE TEMP TABLE reception_payments_json (document jsonb);

-- Chargement depuis les fichiers
\copy reception_customers FROM '/s1/donnees/customers.csv' WITH (FORMAT csv, HEADER true)
\copy reception_orders FROM '/s1/donnees/orders.csv' WITH (FORMAT csv, HEADER true)
\copy reception_order_items FROM '/s1/donnees/order_items.csv' WITH (FORMAT csv, HEADER true)
\copy reception_payments_json (document) FROM '/s1/donnees/payments.ndjson' WITH (FORMAT csv, QUOTE E'\x01', DELIMITER E'\x02')

-- Dépliage du JSON des paiements
CREATE TEMP TABLE reception_payments AS
SELECT p.payment_id, p.order_id, p.paid_on, p.amount_cents, p.status
FROM reception_payments_json
CROSS JOIN LATERAL jsonb_to_record(document) AS p(payment_id integer, order_id integer, paid_on date, amount_cents integer, status text);

-- ==========================================
-- 2. DÉFINITION DU SCHÉMA MÉTIER
-- ==========================================
CREATE TABLE customers (
    customer_id integer PRIMARY KEY,
    customer_name text NOT NULL,
    city text
);

CREATE TABLE orders (
    order_id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES customers(customer_id),
    ordered_on date NOT NULL,
    status text NOT NULL CHECK (status IN ('completed', 'pending', 'cancelled'))
);

CREATE TABLE order_items (
    order_item_id integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES orders(order_id),
    product_id integer NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price_cents integer NOT NULL CHECK (unit_price_cents >= 0)
);

CREATE TABLE payments (
    payment_id integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES orders(order_id),
    paid_on date NOT NULL,
    amount_cents integer NOT NULL,
    status text NOT NULL CHECK (status IN ('captured', 'pending'))
);

-- ==========================================
-- 3. INTÉGRATION ET FILTRAGE DES ANOMALIES
-- ==========================================
INSERT INTO customers (customer_id, customer_name, city)
SELECT DISTINCT customer_id, customer_name, city FROM reception_customers;

INSERT INTO orders (order_id, customer_id, ordered_on, status)
SELECT DISTINCT order_id, customer_id, ordered_on, status 
FROM reception_orders
WHERE customer_id IN (SELECT customer_id FROM customers);

INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price_cents)
SELECT DISTINCT order_item_id, order_id, product_id, quantity, unit_price_cents
FROM reception_order_items
WHERE order_id IN (SELECT order_id FROM orders); -- Rejette l'orphelin (commande 9999)

INSERT INTO payments (payment_id, order_id, paid_on, amount_cents, status)
SELECT DISTINCT payment_id, order_id, paid_on, amount_cents, status
FROM reception_payments
WHERE order_id IN (SELECT order_id FROM orders);

COMMIT;