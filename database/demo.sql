-- Entirely fictional presentation data, applied only to an empty prototype schema.
INSERT INTO prototype.clients (id,name,contact,status,screening) VALUES
 (1,'Марина Александровна Лесная','+7 (000) 000-00-01','На программе','Демонстрационная анкета. Данные вымышлены.'),
 (2,'Виктор Павлович Озеров','+7 (000) 000-00-02','Ознакомительные занятия',NULL),
 (3,'Елена Сергеевна Светлова','elena@example.com','Первое знакомство',NULL),
 (4,'Андрей Игоревич Мирный','andrey@example.com','На программе',NULL),
 (5,'Наталья Олеговна Соснова','+7 (000) 000-00-05','Ознакомительные занятия',NULL);
INSERT INTO prototype.employees (id,name,role,specialization,status) VALUES
 (1,'Ольга Викторовна Речная','Специалист','Ознакомительные занятия','Работает'),
 (2,'Алексей Сергеевич Луговой','Специалист','Сопровождение программ','Работает'),
 (3,'Ирина Петровна Полевая','Администратор','Работа с клиентами','Работает');
INSERT INTO prototype.nomenclature (id,name,type,category,description) VALUES
 (1,'Ознакомительное занятие','Услуга','Занятия','Знакомство с центром и программами'),
 (2,'Индивидуальное занятие','Услуга','Сопровождение','Занятие со специалистом'),
 (3,'Набор для домашних занятий','Товар','Аксессуары','Учебный пример товара');
INSERT INTO prototype.programs (id,name,description,included_services,price,duration) VALUES
 (1,'Бережный старт','Программа знакомства с регулярными занятиями','4 индивидуальных занятия',12000,'1 месяц'),
 (2,'Активный ритм','Регулярные занятия и сопровождение','8 индивидуальных занятий',22000,'2 месяца'),
 (3,'Время для себя','Индивидуальная программа сопровождения','12 индивидуальных занятий',32000,'3 месяца');
INSERT INTO prototype.contracts (id,number,client_id,employee_id,program_id,status,start_date,end_date) VALUES
 (1,'Д-001',1,2,1,'Действует',CURRENT_DATE-7,CURRENT_DATE+23),
 (2,'Д-002',4,2,2,'Действует',CURRENT_DATE-14,CURRENT_DATE+46);
INSERT INTO prototype.visits (client_id,employee_id,starts_at,purpose,contract_id,status) VALUES
 (3,1,CURRENT_DATE + INTERVAL '1 day 10 hours','Первое ознакомительное занятие',NULL,'Запланирован'),
 (2,1,CURRENT_DATE + INTERVAL '1 day 11 hours 30 minutes','Ознакомительное занятие № 2',NULL,'Запланирован'),
 (1,2,CURRENT_DATE + INTERVAL '1 day 14 hours','Занятие по программе',1,'Подтверждён'),
 (5,1,CURRENT_DATE + INTERVAL '2 days 10 hours','Ознакомительное занятие № 3',NULL,'Запланирован');
INSERT INTO prototype.sales (id,number,client_id,employee_id,sold_at,amount,payment_status,positions) VALUES
 (1,'П-001',1,3,CURRENT_TIMESTAMP,2500,'Оплачено','[{"номенклатура":"Набор для домашних занятий","количество":1,"цена":2500,"сумма":2500}]');
INSERT INTO prototype.payments (receipt_number,basis,amount,method,paid_at,status) VALUES
 ('Ч-001','Продажа П-001',2500,'Банковская карта',CURRENT_TIMESTAMP,'Оплачено'),
 ('Ч-002','Договор Д-001',12000,'Банковская карта',CURRENT_TIMESTAMP,'Оплачено');
INSERT INTO prototype.suppliers (id,name) VALUES (1,'Демо-поставщик «Гармония»');
INSERT INTO prototype.orders (number,supplier_id,delivery_date,positions,amount) VALUES
 ('З-001',1,CURRENT_DATE+3,'[{"товар":"Набор для домашних занятий","количество":10,"закупочная_цена":1500,"сумма":15000}]',15000);
INSERT INTO prototype.stock (item_id,name,quantity) VALUES (3,'Набор для домашних занятий',9);
INSERT INTO prototype.movements (number,basis,amount,incoming,outgoing,item_id) VALUES
 ('ДВ-001','Заказ З-001',15000,10,0,3), ('ДВ-002','Продажа П-001',2500,0,1,3);
INSERT INTO prototype.provided_services (service_id,quantity,amount) VALUES (2,2,6000);
INSERT INTO prototype.service_log (number,service_id,quantity,amount,basis) VALUES
 ('У-001',2,2,6000,'Договор Д-001');
INSERT INTO prototype.employee_activity (employee_id,hours,goods_sold,revenue) VALUES
 (1,24,0,12000),(2,32,0,18000),(3,40,1,2500);
INSERT INTO prototype.work_log (number,basis,employee_id,hours,goods_sold,revenue) VALUES
 ('Р-001','Договор Д-001',2,2,0,6000);
DO $$
DECLARE t TEXT;
BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='prototype' LOOP
  EXECUTE format('SELECT setval(pg_get_serial_sequence(%L, ''id''), COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM prototype.%I', 'prototype.' || t, t);
 END LOOP;
END $$;
