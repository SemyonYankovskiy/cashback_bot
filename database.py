import aiosqlite
from contextlib import asynccontextmanager
from settings import DB_NAME


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_NAME)
    try:
        yield db
    finally:
        await db.close()


# Инициализация базы данных
async def init_db():
    async with get_db() as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                friend_id INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS cashback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                bank_id INTEGER,
                category_id INTEGER,
                percent REAL,
                period TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (bank_id) REFERENCES banks(id),
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')

        # Предзаполнение банков
        await db.executemany('INSERT OR IGNORE INTO banks (name) VALUES (?)', [
            ('Т-банк',),
            ('ВТБ',)
        ])

        # Предзаполнение категорий
        await db.executemany('INSERT OR IGNORE INTO categories (name) VALUES (?)', [
            ('🛍 Все покупки',),
            ('⚽️ Спорттовары',),
            ('🐶 Животные',),
            ('💊 Аптеки',),
            ('⛽️ Заправки',),
            ('🛒 Супермаркеты',),
            ('💐 Цветы',),
            ('💋 Красота',),
            ('🎮 Развлечения',),
            ('🎭 Искусство',),
            ('🍔 Фаст-фуд',),
            ('🍽 Рестораны',)
        ])

        await db.commit()


# Методы доступа к данным

async def register_user(user_id: int):
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()


async def get_banks():
    async with get_db() as db:
        cursor = await db.execute("SELECT id, name FROM banks")
        return await cursor.fetchall()


async def get_categories():
    async with get_db() as db:
        cursor = await db.execute("SELECT id, name FROM categories")
        return await cursor.fetchall()


async def add_categories(new_cat):
    async with get_db() as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (new_cat,))
        await db.commit()


async def delete_category(cat_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        await db.commit()

async def insert_cashback(user_id: int, bank_id: int, category_id: int, percent: float, period: str):
    async with get_db() as db:
        await db.execute('''
            INSERT INTO cashback (user_id, bank_id, category_id, percent, period)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, bank_id, category_id, percent, period))
        await db.commit()


async def get_user_friend(user_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT friend_id FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else None


async def get_cashbacks(user_id: int):
    async with get_db() as db:
        cursor = await db.execute('''
            SELECT cashback.period, banks.name, categories.name, cashback.percent
            FROM cashback
            JOIN banks ON cashback.bank_id = banks.id
            JOIN categories ON cashback.category_id = categories.id
            WHERE cashback.user_id = ?
            ORDER BY cashback.period, banks.name
        ''', (user_id,))
        return await cursor.fetchall()


async def get_user_periods(user_id: int, bank_id: int, category_id: int, periods: list):
    placeholders = ', '.join('?' for _ in periods)
    async with get_db() as db:
        cursor = await db.execute(f'''
            SELECT DISTINCT period FROM cashback
            WHERE user_id = ? AND bank_id = ? AND category_id = ? AND period IN ({placeholders})
        ''', (user_id, bank_id, category_id, *periods))
        return [row[0] async for row in cursor]


async def get_user_all_periods(user_id: int, bank_id: int, category_id: int):
    async with get_db() as db:
        cursor = await db.execute('''
            SELECT DISTINCT period FROM cashback
            WHERE user_id = ? AND bank_id = ? AND category_id = ?
        ''', (user_id, bank_id, category_id))
        return [row[0] async for row in cursor]


async def set_user_friend(user_id: int, friend_id: int):
    async with get_db() as db:
        await db.execute('''
            INSERT INTO users (user_id, friend_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET friend_id=excluded.friend_id
        ''', (user_id, friend_id))
        await db.commit()

# Получить категории, по которым есть кешбэки у пользователя
async def get_user_categories(user_id: int) -> list[tuple[int, str]]:
    async with get_db() as db:
        cursor = await db.execute('''
            SELECT DISTINCT categories.id, categories.name
            FROM cashback
            JOIN categories ON cashback.category_id = categories.id
            WHERE cashback.user_id = ?
            ORDER BY categories.name
        ''', (user_id,))
        return await cursor.fetchall()

# Удалить кешбэки по списку категорий
async def delete_user_categories(user_id: int, category_ids: list[int]):
    if not category_ids:
        return
    placeholders = ','.join('?' for _ in category_ids)
    async with get_db() as db:
        await db.execute(f'''
            DELETE FROM cashback
            WHERE user_id = ? AND category_id IN ({placeholders})
        ''', (user_id, *category_ids))
        await db.commit()

# Удалить все кешбэки пользователя
async def delete_all_cashbacks(user_id: int):
    async with get_db() as db:
        await db.execute('DELETE FROM cashback WHERE user_id = ?', (user_id,))
        await db.commit()


async def get_user_bank_category_pairs(user_id):
    async with get_db() as db:
        cursor = await db.execute('''
            SELECT id, 
                   (SELECT name FROM banks WHERE banks.id = cashback.bank_id) AS bank_name,
                   (SELECT name FROM categories WHERE categories.id = cashback.category_id) AS cat_name,
                   percent
            FROM cashback
            WHERE user_id = ?
        ''', (user_id,))
        return await cursor.fetchall()


async def delete_cashback_entries(user_id, entry_ids):
    if not entry_ids:
        return
    placeholders = ','.join('?' for _ in entry_ids)
    async with get_db() as db:
        await db.execute(f'''
            DELETE FROM cashback
            WHERE user_id = ? AND id IN ({placeholders})
        ''', (user_id, *entry_ids))
        await db.commit()