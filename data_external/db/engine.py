# data_external/db/engine.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# 数据库文件存放在 data_external/db/ 目录下，或者项目根目录
# 这里我们选择放在 db 目录下，方便管理
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "external_data_cache.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)
    print(f"✅ 外部数据缓存库已初始化：{DB_PATH}")

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()