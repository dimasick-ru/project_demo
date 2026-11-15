"""Fields from docs/Рецепты долголетия.vsdx; no posting rules are implied."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"
    required: bool = False
    reference: str | None = None


@dataclass(frozen=True)
class Entity:
    key: str
    title: str
    group: str
    fields: tuple[Field, ...]
    summary: str


def f(
    key: str,
    label: str,
    kind: str = "text",
    required: bool = False,
    reference: str | None = None,
) -> Field:
    return Field(key, label, kind, required, reference)


ENTITIES = {
    e.key: e
    for e in (
        Entity(
            "clients",
            "Клиенты",
            "Работа с клиентами",
            (
                f("name", "ФИО", required=True),
                f("contact", "Контактная информация"),
                f("status", "Статус"),
                f("screening", "Анкета здоровья / скрининг", "textarea"),
            ),
            "Контакты, статус и информация о клиенте",
        ),
        Entity(
            "visits",
            "Визиты",
            "Работа с клиентами",
            (
                f("client_id", "Клиент", "reference", True, "clients"),
                f("employee_id", "Сотрудник", "reference", False, "employees"),
                f("starts_at", "Дата и время", "datetime-local", True),
                f("purpose", "Цель визита"),
                f(
                    "contract_id",
                    "Договор при наличии",
                    "reference",
                    False,
                    "contracts",
                ),
                f("status", "Статус"),
            ),
            "Расписание встреч и ознакомительных занятий",
        ),
        Entity(
            "programs",
            "Программы",
            "Работа с клиентами",
            (
                f("name", "Наименование", required=True),
                f("description", "Описание", "textarea"),
                f("included_services", "Входящие услуги", "textarea"),
                f("price", "Стоимость, ₽", "money", True),
                f("duration", "Длительность"),
            ),
            "Программы сопровождения и их стоимость",
        ),
        Entity(
            "contracts",
            "Договоры клиентов",
            "Работа с клиентами",
            (
                f("number", "Номер", required=True),
                f("client_id", "Клиент", "reference", True, "clients"),
                f("employee_id", "Сотрудник", "reference", False, "employees"),
                f("program_id", "Программа", "reference", True, "programs"),
                f("status", "Статус"),
                f("start_date", "Дата начала", "date"),
                f("end_date", "Дата окончания", "date"),
            ),
            "Программы клиентов, сроки и статусы договоров",
        ),
        Entity(
            "sales",
            "Продажи",
            "Продажи и оплата",
            (
                f("number", "Номер", required=True),
                f("client_id", "Клиент", "reference", False, "clients"),
                f("employee_id", "Сотрудник", "reference", False, "employees"),
                f("sold_at", "Дата и время", "datetime-local"),
                f("amount", "Сумма, ₽", "money"),
                f("payment_status", "Статус оплаты"),
                f("positions", "Позиции", "json"),
            ),
            "Продажи товаров и услуг клиентам",
        ),
        Entity(
            "payments",
            "Оплата",
            "Продажи и оплата",
            (
                f("receipt_number", "Номер чека", required=True),
                f("basis", "Документ-основание"),
                f("amount", "Сумма, ₽", "money", True),
                f("method", "Способ оплаты"),
                f("paid_at", "Дата и время", "datetime-local"),
                f("status", "Статус"),
            ),
            "Чеки, способы оплаты и основания платежей",
        ),
        Entity(
            "nomenclature",
            "Номенклатура",
            "Товары и склад",
            (
                f("name", "Наименование", required=True),
                f("type", "Тип"),
                f("category", "Категория"),
                f("description", "Описание", "textarea"),
            ),
            "Единый справочник товаров и услуг",
        ),
        Entity(
            "suppliers",
            "Поставщики",
            "Товары и склад",
            (f("name", "Наименование", required=True),),
            "Справочник поставщиков товаров",
        ),
        Entity(
            "orders",
            "Заказы товаров",
            "Товары и склад",
            (
                f("number", "Номер", required=True),
                f("supplier_id", "Поставщик", "reference", True, "suppliers"),
                f("delivery_date", "Дата поставки", "date"),
                f("positions", "Список товаров", "json"),
                f("amount", "Общая сумма, ₽", "money"),
            ),
            "Заказы поставщикам и ожидаемые поставки",
        ),
        Entity(
            "stock",
            "Остатки на складе",
            "Товары и склад",
            (
                f("item_id", "ID товара", "reference", True, "nomenclature"),
                f("name", "Наименование", required=True),
                f("quantity", "Количество", "number", True),
            ),
            "Текущие остатки товаров — ручной ввод в прототипе",
        ),
        Entity(
            "movements",
            "Журнал движений товаров",
            "Товары и склад",
            (
                f("number", "Номер", required=True),
                f("basis", "Документ-основание"),
                f("amount", "Сумма, ₽", "money"),
                f("incoming", "Количество: приход", "number"),
                f("outgoing", "Количество: расход", "number"),
                f("item_id", "Номенклатура", "reference", True, "nomenclature"),
            ),
            "Регистрация прихода и расхода товаров",
        ),
        Entity(
            "provided_services",
            "Предоставленные услуги",
            "Услуги",
            (
                f("service_id", "Услуга", "reference", True, "nomenclature"),
                f("quantity", "Количество", "number"),
                f("amount", "Сумма, ₽", "money"),
            ),
            "Учёт предоставленных услуг",
        ),
        Entity(
            "service_log",
            "Журнал предоставления услуг",
            "Услуги",
            (
                f("number", "Номер", required=True),
                f("service_id", "Услуга", "reference", True, "nomenclature"),
                f("quantity", "Количество", "number"),
                f("amount", "Сумма, ₽", "money"),
                f("basis", "Документ-основание"),
            ),
            "Записи об услугах и документах-основаниях",
        ),
        Entity(
            "employees",
            "Сотрудники",
            "Команда",
            (
                f("name", "ФИО", required=True),
                f("role", "Должность / роль"),
                f("specialization", "Специализация"),
                f("status", "Статус"),
            ),
            "Команда центра и специализации сотрудников",
        ),
        Entity(
            "employee_activity",
            "Активность сотрудников",
            "Команда",
            (
                f("employee_id", "ФИО", "reference", True, "employees"),
                f("hours", "Выработано часов", "number"),
                f("goods_sold", "Продано товаров", "number"),
                f("revenue", "Выручка, ₽", "money"),
            ),
            "Показатели работы команды — ручной ввод в прототипе",
        ),
        Entity(
            "work_log",
            "Регистрация работы сотрудников",
            "Команда",
            (
                f("number", "Номер", required=True),
                f("basis", "Документ-основание"),
                f("employee_id", "ФИО", "reference", True, "employees"),
                f("hours", "Выработано часов", "number"),
                f("goods_sold", "Продано товаров", "number"),
                f("revenue", "Выручка, ₽", "money"),
            ),
            "Регистрация работы по документам-основаниям",
        ),
    )
}
