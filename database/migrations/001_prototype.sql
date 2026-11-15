-- Additive prototype schema; existing public.items remains untouched.
-- References are represented by IDs as in the source diagram, without added FKs.
CREATE SCHEMA IF NOT EXISTS prototype;
CREATE TABLE IF NOT EXISTS prototype.clients (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, contact TEXT, status TEXT, screening TEXT
);
CREATE TABLE IF NOT EXISTS prototype.employees (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, role TEXT, specialization TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS prototype.nomenclature (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, type TEXT, category TEXT, description TEXT
);
CREATE TABLE IF NOT EXISTS prototype.programs (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT, included_services TEXT,
 price NUMERIC(14,2) NOT NULL, duration TEXT
);
CREATE TABLE IF NOT EXISTS prototype.contracts (
 id BIGSERIAL PRIMARY KEY, number TEXT NOT NULL, client_id BIGINT NOT NULL,
 employee_id BIGINT, program_id BIGINT NOT NULL, status TEXT, start_date DATE, end_date DATE
);
CREATE TABLE IF NOT EXISTS prototype.visits (
 id BIGSERIAL PRIMARY KEY, client_id BIGINT NOT NULL, employee_id BIGINT,
 starts_at TIMESTAMP NOT NULL, purpose TEXT, contract_id BIGINT, status TEXT
);
CREATE TABLE IF NOT EXISTS prototype.sales (
 id BIGSERIAL PRIMARY KEY, number TEXT NOT NULL, client_id BIGINT, employee_id BIGINT,
 sold_at TIMESTAMP, amount NUMERIC(14,2), payment_status TEXT, positions JSONB
);
CREATE TABLE IF NOT EXISTS prototype.payments (
 id BIGSERIAL PRIMARY KEY, receipt_number TEXT NOT NULL, basis TEXT, amount NUMERIC(14,2) NOT NULL,
 method TEXT, paid_at TIMESTAMP, status TEXT
);
CREATE TABLE IF NOT EXISTS prototype.suppliers (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prototype.orders (
 id BIGSERIAL PRIMARY KEY, number TEXT NOT NULL, supplier_id BIGINT NOT NULL,
 delivery_date DATE, positions JSONB, amount NUMERIC(14,2)
);
CREATE TABLE IF NOT EXISTS prototype.stock (
 id BIGSERIAL PRIMARY KEY, item_id BIGINT NOT NULL, name TEXT NOT NULL, quantity NUMERIC(14,4) NOT NULL
);
CREATE TABLE IF NOT EXISTS prototype.movements (
 id BIGSERIAL PRIMARY KEY, number TEXT NOT NULL, basis TEXT, amount NUMERIC(14,2),
 incoming NUMERIC(14,4), outgoing NUMERIC(14,4), item_id BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS prototype.provided_services (
 id BIGSERIAL PRIMARY KEY, service_id BIGINT NOT NULL, quantity NUMERIC(14,4), amount NUMERIC(14,2)
);
CREATE TABLE IF NOT EXISTS prototype.service_log (
 id BIGSERIAL PRIMARY KEY, number TEXT NOT NULL, service_id BIGINT NOT NULL,
 quantity NUMERIC(14,4), amount NUMERIC(14,2), basis TEXT
);
CREATE TABLE IF NOT EXISTS prototype.employee_activity (
 id BIGSERIAL PRIMARY KEY, employee_id BIGINT NOT NULL, hours NUMERIC(14,4),
 goods_sold NUMERIC(14,4), revenue NUMERIC(14,2)
);
CREATE TABLE IF NOT EXISTS prototype.work_log (
 id BIGSERIAL PRIMARY KEY, number TEXT NOT NULL, basis TEXT, employee_id BIGINT NOT NULL,
 hours NUMERIC(14,4), goods_sold NUMERIC(14,4), revenue NUMERIC(14,2)
);
