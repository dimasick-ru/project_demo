CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(10, 2) NOT NULL
);

INSERT INTO items (name, price) VALUES
('Item 1', 10.00),
('Item 2', 20.00),
('Item 3', 30.00);