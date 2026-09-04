"""اتصال قاعدة البيانات."""

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import DB_NAME, MONGO_URL


# MongoDB Client
client = AsyncIOMotorClient(MONGO_URL)

db = client[DB_NAME]
