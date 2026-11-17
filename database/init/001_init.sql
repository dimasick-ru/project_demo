-- Рецепты долголетия: предварительная схема БД, версия 3 (приёмка и вычисляемые журналы).
-- Основа: сущности Visio + согласованные заявки и позиции заявок.
-- Предположения (статусы, обязательность, детализация) требуют проверки.
-- Документные номера имеют возможные пропуски при откатах транзакций.
-- Статусы completed/posted и часовой пояс UTC для отчётности пока предварительные.
-- Проверка переприёмки, товарных типов и отрицательных остатков должна быть
-- реализована атомарно в Python-сервисе/транзакциях или триггерах БД.
-- Выполнять на НОВОЙ базе: CREATE TABLE без IF NOT EXISTS.
BEGIN;

CREATE TABLE clients (
    client_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    client_status TEXT NOT NULL DEFAULT 'active',
    health_screening JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE employees (
    employee_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name TEXT NOT NULL,
    role_name TEXT NOT NULL,
    specialization TEXT,
    employee_status TEXT NOT NULL DEFAULT 'active'
);

-- Общая номенклатура: услуги и товары. Программы хранятся отдельно.
CREATE TABLE nomenclature (
    nomenclature_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK (item_type IN ('service', 'product')),
    category TEXT,
    description TEXT,
    price NUMERIC(12,2) CHECK (price >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE programs (
    program_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    duration_days INTEGER CHECK (duration_days > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE program_services (
    program_id BIGINT NOT NULL REFERENCES programs(program_id),
    nomenclature_id BIGINT NOT NULL REFERENCES nomenclature(nomenclature_id),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    PRIMARY KEY (program_id, nomenclature_id)
);
-- Правило «program_services содержит только service» проверяется сервисом
-- или дополнительным триггером (обычный FOREIGN KEY не проверяет item_type).

-- A1. Клиент может иметь любое количество заявок.
CREATE TABLE applications (
    application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(client_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    employee_id BIGINT REFERENCES employees(employee_id),
    status TEXT NOT NULL DEFAULT 'new',
    comment TEXT
);

-- Позиция заявки: либо программа, либо номенклатура (услуга/товар).
CREATE TABLE application_items (
    application_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES applications(application_id),
    nomenclature_id BIGINT REFERENCES nomenclature(nomenclature_id),
    program_id BIGINT REFERENCES programs(program_id),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    CHECK (num_nonnulls(nomenclature_id, program_id) = 1)
);

CREATE SEQUENCE contract_number_seq START WITH 1;

CREATE TABLE client_contracts (
    contract_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contract_number TEXT NOT NULL UNIQUE DEFAULT (
        'RD-' || lpad(nextval('contract_number_seq')::TEXT, 8, '0')
    ),
    client_id BIGINT NOT NULL REFERENCES clients(client_id),
    employee_id BIGINT REFERENCES employees(employee_id),
    program_id BIGINT REFERENCES programs(program_id),
    application_id BIGINT REFERENCES applications(application_id),
    status TEXT NOT NULL DEFAULT 'draft',
    start_date DATE,
    end_date DATE,
    agreed_price NUMERIC(12,2) CHECK (agreed_price >= 0),
    CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE visits (
    visit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(client_id),
    employee_id BIGINT REFERENCES employees(employee_id),
    application_id BIGINT REFERENCES applications(application_id),
    contract_id BIGINT REFERENCES client_contracts(contract_id),
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CHECK (finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)),
    purpose TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    intro_lesson_number SMALLINT CHECK (intro_lesson_number BETWEEN 1 AND 4)
);

CREATE TABLE sales (
    sale_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(client_id),
    employee_id BIGINT REFERENCES employees(employee_id),
    application_id BIGINT REFERENCES applications(application_id),
    sold_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'created'
);

CREATE TABLE sale_items (
    sale_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sale_id BIGINT NOT NULL REFERENCES sales(sale_id),
    nomenclature_id BIGINT NOT NULL REFERENCES nomenclature(nomenclature_id),
    quantity NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(14,2) GENERATED ALWAYS AS (round(quantity * unit_price, 2)) STORED
);

-- Платёж относится к договору или продаже. Номер чека можно добавить позже.
CREATE TABLE payments (
    payment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contract_id BIGINT REFERENCES client_contracts(contract_id),
    sale_id BIGINT REFERENCES sales(sale_id),
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    payment_method TEXT NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'pending',
    receipt_number TEXT,
    CHECK (num_nonnulls(contract_id, sale_id) = 1)
);

CREATE TABLE suppliers (
    supplier_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    contact_info TEXT
);

CREATE TABLE purchase_orders (
    purchase_order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES suppliers(supplier_id),
    delivery_date DATE,
    status TEXT NOT NULL DEFAULT 'created'
);

CREATE TABLE purchase_order_items (
    purchase_order_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_orders(purchase_order_id),
    nomenclature_id BIGINT NOT NULL REFERENCES nomenclature(nomenclature_id),
    quantity NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    purchase_unit_price NUMERIC(12,2) NOT NULL CHECK (purchase_unit_price >= 0),
    line_total NUMERIC(14,2) GENERATED ALWAYS AS (round(quantity * purchase_unit_price, 2)) STORED,
    UNIQUE (purchase_order_item_id, purchase_order_id)
);

-- Фактическая приёмка товаров по заказу поставщику.
-- Один заказ может быть принят несколькими партиями.
CREATE SEQUENCE goods_receipt_number_seq START WITH 1;
CREATE TABLE goods_receipts (
    receipt_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    receipt_number TEXT NOT NULL UNIQUE DEFAULT
        ('GR-' || lpad(nextval('goods_receipt_number_seq')::TEXT, 8, '0')),
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_orders(purchase_order_id),
    employee_id BIGINT NOT NULL REFERENCES employees(employee_id),
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted', 'cancelled')),
    comment TEXT,
    UNIQUE (receipt_id, purchase_order_id)
);

CREATE TABLE goods_receipt_items (
    receipt_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    receipt_id BIGINT NOT NULL,
    purchase_order_id BIGINT NOT NULL,
    purchase_order_item_id BIGINT NOT NULL,
    quantity NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    FOREIGN KEY (receipt_id, purchase_order_id)
        REFERENCES goods_receipts(receipt_id, purchase_order_id),
    FOREIGN KEY (purchase_order_item_id, purchase_order_id)
        REFERENCES purchase_order_items(purchase_order_item_id, purchase_order_id)
);

CREATE TABLE provided_services (
    provided_service_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(client_id),
    employee_id BIGINT REFERENCES employees(employee_id),
    nomenclature_id BIGINT NOT NULL REFERENCES nomenclature(nomenclature_id),
    visit_id BIGINT REFERENCES visits(visit_id),
    contract_id BIGINT REFERENCES client_contracts(contract_id),
    provided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    quantity NUMERIC(12,3) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    amount NUMERIC(12,2) CHECK (amount >= 0)
);

-- Журналы не хранят дубли: вычисляются из первичных документов.
CREATE VIEW service_journal AS
SELECT ps.provided_service_id, ps.client_id, ps.employee_id,
       ps.nomenclature_id, ps.visit_id, ps.contract_id,
       ps.provided_at, ps.quantity, ps.amount
FROM provided_services AS ps;

-- Приход только по проведённым приёмкам; расход только по завершённым продажам.
-- Возвраты и списания потребуют отдельных первичных документов.
CREATE VIEW stock_movements AS
SELECT 'receipt'::TEXT AS source_type,
       gri.receipt_item_id AS source_item_id,
       poi.nomenclature_id,
       gr.received_at AS moved_at,
       gri.quantity AS quantity_delta
FROM goods_receipt_items AS gri
JOIN goods_receipts AS gr ON gr.receipt_id = gri.receipt_id
JOIN purchase_order_items AS poi ON poi.purchase_order_item_id = gri.purchase_order_item_id
WHERE gr.status = 'posted'
UNION ALL
SELECT 'sale'::TEXT AS source_type,
       si.sale_item_id AS source_item_id,
       si.nomenclature_id,
       s.sold_at AS moved_at,
       -si.quantity AS quantity_delta
FROM sale_items AS si
JOIN sales AS s ON s.sale_id = si.sale_id
JOIN nomenclature AS n ON n.nomenclature_id = si.nomenclature_id
WHERE s.status = 'completed' AND n.item_type = 'product';

CREATE VIEW stock_balances AS
SELECT n.nomenclature_id, n.name,
       COALESCE(SUM(sm.quantity_delta), 0)::NUMERIC(14,3) AS quantity
FROM nomenclature AS n
LEFT JOIN stock_movements AS sm ON sm.nomenclature_id = n.nomenclature_id
WHERE n.item_type = 'product'
GROUP BY n.nomenclature_id, n.name;

-- Время работы вычисляется по фактическим началу и окончанию визита.
-- Вне визитов рабочее время пока не учитывается: нужен первичный документ.
CREATE VIEW employee_work_log AS
SELECT v.visit_id, v.employee_id,
       (v.started_at AT TIME ZONE 'UTC')::DATE AS work_date,
       v.started_at, v.finished_at,
       round((EXTRACT(EPOCH FROM (v.finished_at - v.started_at)) / 3600)::NUMERIC, 2) AS hours_worked
FROM visits AS v
WHERE v.employee_id IS NOT NULL AND v.status = 'completed'
  AND v.started_at IS NOT NULL AND v.finished_at IS NOT NULL;

-- Сводка активности: завершённые продажи, оказанные услуги и часы по визитам.
-- Выручка пока определяется как стоимость завершённых продаж, не оплаты.
CREATE VIEW employee_activities AS
WITH sales_by_day AS (
    SELECT s.employee_id, (s.sold_at AT TIME ZONE 'UTC')::DATE AS activity_date,
           COUNT(DISTINCT s.sale_id) AS sales_count,
           COALESCE(SUM(si.quantity) FILTER (WHERE n.item_type = 'product'), 0) AS goods_sold,
           COALESCE(SUM(si.line_total), 0) AS sales_revenue
    FROM sales AS s
    JOIN sale_items AS si ON si.sale_id = s.sale_id
    JOIN nomenclature AS n ON n.nomenclature_id = si.nomenclature_id
    WHERE s.employee_id IS NOT NULL AND s.status = 'completed'
    GROUP BY s.employee_id, (s.sold_at AT TIME ZONE 'UTC')::DATE
),
services_by_day AS (
    SELECT ps.employee_id, (ps.provided_at AT TIME ZONE 'UTC')::DATE AS activity_date,
           COUNT(*) AS services_count
    FROM provided_services AS ps
    WHERE ps.employee_id IS NOT NULL
    GROUP BY ps.employee_id, (ps.provided_at AT TIME ZONE 'UTC')::DATE
),
work_by_day AS (
    SELECT employee_id, work_date AS activity_date, SUM(hours_worked) AS hours_worked
    FROM employee_work_log GROUP BY employee_id, work_date
),
dates AS (
    SELECT employee_id, activity_date FROM sales_by_day
    UNION SELECT employee_id, activity_date FROM services_by_day
    UNION SELECT employee_id, activity_date FROM work_by_day
)
SELECT d.employee_id, d.activity_date,
       COALESCE(w.hours_worked, 0)::NUMERIC(10,2) AS hours_worked,
       COALESCE(s.sales_count, 0) AS sales_count,
       COALESCE(ps.services_count, 0) AS services_count,
       COALESCE(s.goods_sold, 0)::NUMERIC(14,3) AS goods_sold,
       COALESCE(s.sales_revenue, 0)::NUMERIC(14,2) AS sales_revenue
FROM dates AS d
LEFT JOIN sales_by_day AS s USING (employee_id, activity_date)
LEFT JOIN services_by_day AS ps USING (employee_id, activity_date)
LEFT JOIN work_by_day AS w USING (employee_id, activity_date);

CREATE INDEX idx_applications_client ON applications(client_id);
CREATE INDEX idx_applications_created ON applications(created_at DESC);
CREATE INDEX idx_application_items_application ON application_items(application_id);
CREATE INDEX idx_contracts_client ON client_contracts(client_id);
CREATE INDEX idx_visits_client_time ON visits(client_id, scheduled_at);
CREATE INDEX idx_sales_client_time ON sales(client_id, sold_at DESC);
CREATE INDEX idx_payments_contract ON payments(contract_id);
CREATE INDEX idx_payments_sale ON payments(sale_id);
CREATE INDEX idx_receipts_order ON goods_receipts(purchase_order_id);
CREATE INDEX idx_receipt_items_receipt ON goods_receipt_items(receipt_id);
CREATE INDEX idx_receipt_items_order_item ON goods_receipt_items(purchase_order_item_id);
CREATE INDEX idx_sales_employee_time ON sales(employee_id, sold_at DESC);
CREATE INDEX idx_provided_services_client_time ON provided_services(client_id, provided_at DESC);

COMMIT;
