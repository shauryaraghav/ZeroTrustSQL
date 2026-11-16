CREATE TABLE customers (id serial PRIMARY KEY, name text NOT NULL, country text NOT NULL, created_at date NOT NULL, email text NOT NULL, phone text NOT NULL);
CREATE TABLE employees (id serial PRIMARY KEY, name text NOT NULL, department text NOT NULL, salary numeric(10,2) NOT NULL);
CREATE TABLE products  (id serial PRIMARY KEY, name text NOT NULL, category text NOT NULL, price numeric(10,2) NOT NULL);
CREATE TABLE orders    (id serial PRIMARY KEY, customer_id int NOT NULL REFERENCES customers(id), ordered_at date NOT NULL, status text NOT NULL);
CREATE TABLE order_items (id serial PRIMARY KEY, order_id int NOT NULL REFERENCES orders(id), product_id int NOT NULL REFERENCES products(id), quantity int NOT NULL, unit_price numeric(10,2) NOT NULL);

INSERT INTO customers (name, country, created_at, email, phone)
SELECT 'Customer ' || g, (ARRAY['India','USA','Germany','Brazil','Japan','UK'])[1 + g % 6], current_date - (g * 7 % 700), 'customer' || g || '@example.com', '+91 98' || lpad(g::text, 8, '0') FROM generate_series(1, 120) g;
INSERT INTO employees (name, department, salary) SELECT 'Employee ' || g, (ARRAY['Sales','Engineering','Support'])[1 + g % 3], 40000 + g * 2500 FROM generate_series(1, 20) g;
INSERT INTO products (name, category, price)
SELECT 'Product ' || g, (ARRAY['Hardware','Software','Services','Accessories'])[1 + g % 4], (10 + (g * 37) % 490)::numeric FROM generate_series(1, 40) g;
INSERT INTO orders (customer_id, ordered_at, status)
SELECT 1 + (g * 7) % 120, current_date - (g * 3 % 120), (ARRAY['completed','completed','completed','shipped','cancelled'])[1 + g % 5] FROM generate_series(1, 1500) g;
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT o.id, p.id, 1 + (o.id + p.id) % 5, p.price
FROM orders o JOIN products p ON p.id = 1 + (o.id * 3) % 40 OR p.id = 1 + (o.id * 11) % 40;

CREATE ROLE bi_readonly LOGIN PASSWORD 'readonly_pw';
GRANT CONNECT ON DATABASE shop TO bi_readonly;
GRANT USAGE ON SCHEMA public TO bi_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_readonly;
ALTER ROLE bi_readonly SET default_transaction_read_only = on;
ALTER ROLE bi_readonly SET statement_timeout = '5s';
ALTER ROLE bi_readonly CONNECTION LIMIT 10;
