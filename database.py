import asyncpg
import json
import logging
from datetime import datetime, timedelta
from config import DATABASE_URL

pool = None

async def init_db():
    global pool
    try:
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=5,
            max_size=20, # Adjust based on VPS resources
            command_timeout=60
        )
        
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    subscription_end TIMESTAMP,
                    trial_used BOOLEAN DEFAULT FALSE,
                    balance DOUBLE PRECISION DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS connections (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    connection_id TEXT UNIQUE,
                    chat_id BIGINT,
                    chat_title TEXT,
                    chat_username TEXT,
                    permissions JSONB,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS business_messages (
                    id BIGSERIAL PRIMARY KEY,
                    connection_id TEXT,
                    message_id BIGINT,
                    chat_id BIGINT,
                    chat_title TEXT,
                    chat_username TEXT,
                    from_user_id BIGINT,
                    from_username TEXT,
                    text TEXT,
                    media_type TEXT,
                    media_file_id TEXT,
                    date TIMESTAMP,
                    is_cached BOOLEAN DEFAULT FALSE,
                    UNIQUE(connection_id, message_id)
                );
                
                -- Indexes for high performance
                CREATE INDEX IF NOT EXISTS idx_bm_conn_msg ON business_messages(connection_id, message_id);
                CREATE INDEX IF NOT EXISTS idx_conn_user ON connections(user_id);
                CREATE INDEX IF NOT EXISTS idx_users_sub_end ON users(subscription_end);
            """)
            logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise

async def close_db():
    global pool
    if pool:
        await pool.close()

def get_db_pool():
    return pool

async def remove_subscription(user_id):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users 
            SET subscription_end = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = $1
        """, user_id)

async def add_user(user_id, username, first_name):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, first_name, subscription_end, balance, updated_at)
            VALUES ($1, $2, $3, $4, 0.0, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE 
            SET username = EXCLUDED.username, 
                first_name = EXCLUDED.first_name,
                updated_at = CURRENT_TIMESTAMP
        """, user_id, username, first_name, datetime.now())

async def get_user(user_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None

async def update_balance(user_id, amount):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users 
            SET balance = balance + $1, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = $2
        """, float(amount), user_id)

async def update_subscription(user_id, days):
    async with pool.acquire() as conn:
        # Transaction to ensure consistency
        async with conn.transaction():
            current_end = await conn.fetchval("SELECT subscription_end FROM users WHERE user_id = $1", user_id)
            
            now = datetime.now()
            if not current_end or current_end < now:
                new_end = now + timedelta(days=days)
            else:
                new_end = current_end + timedelta(days=days)
            
            await conn.execute("""
                UPDATE users 
                SET subscription_end = $1, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = $2
            """, new_end, user_id)

async def set_trial_used(user_id):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET trial_used = TRUE WHERE user_id = $1", user_id)

async def add_connection(user_id, connection_id, chat_id, chat_title, chat_username, permissions):
    is_enabled = permissions.get('is_enabled', True)
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO connections (user_id, connection_id, chat_id, chat_title, chat_username, permissions, is_enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (connection_id) DO UPDATE 
            SET chat_title = EXCLUDED.chat_title,
                chat_username = EXCLUDED.chat_username,
                permissions = EXCLUDED.permissions,
                is_enabled = EXCLUDED.is_enabled
        """, user_id, connection_id, chat_id, chat_title, chat_username, json.dumps(permissions), is_enabled)

async def get_connection(connection_id):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM connections WHERE connection_id = $1", connection_id)
        return dict(row) if row else None
            
async def get_user_connections(user_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM connections WHERE user_id = $1 AND is_enabled = TRUE", user_id)
        return [dict(row) for row in rows]

async def add_message(msg_data):
    async with pool.acquire() as conn:
        try:
            # Ensure date is datetime object and handle timezone if needed
            date_val = msg_data['date']
            if isinstance(date_val, str):
                date_val = datetime.fromisoformat(date_val)
            
            # Remove timezone info if present to match TIMESTAMP column (usually naive in this setup)
            if date_val.tzinfo is not None:
                date_val = date_val.replace(tzinfo=None)
                
            await conn.execute("""
                INSERT INTO business_messages 
                (connection_id, message_id, chat_id, chat_title, chat_username, from_user_id, from_username, text, media_type, media_file_id, date, is_cached)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (connection_id, message_id) DO NOTHING
            """, 
                msg_data['connection_id'], msg_data['message_id'], msg_data['chat_id'], 
                msg_data['chat_title'], msg_data['chat_username'], msg_data['from_user_id'], 
                msg_data['from_username'], msg_data['text'], msg_data['media_type'], 
                msg_data.get('media_file_id'), date_val, msg_data.get('is_cached', False)
            )
        except Exception as e:
            logging.error(f"DB Error adding message: {e}")

async def get_stats():
    async with pool.acquire() as conn:
        conn_count = await conn.fetchval("SELECT COUNT(*) FROM connections WHERE is_enabled = TRUE")
        msg_count = await conn.fetchval("SELECT COUNT(*) FROM business_messages")
        return conn_count, msg_count