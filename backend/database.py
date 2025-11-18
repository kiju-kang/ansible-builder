from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# PostgreSQL 연결 설정 (AWX DB 사용)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://awx:dXtiuURqw5iZDWO0RwyEghptyydvMgSo@172.16.102.169:5432/awx"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 테이블 모델 정의 (ansible_builder_ 접두사로 AWX와 구분)
class AnsibleBuilderPlaybook(Base):
    __tablename__ = "ansible_builder_playbooks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    hosts = Column(String(255), nullable=False, default="all")
    become = Column(Boolean, default=False)
    tasks = Column(Text, nullable=False)  # JSON 형태로 저장
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AnsibleBuilderInventory(Base):
    __tablename__ = "ansible_builder_inventories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AnsibleBuilderExecution(Base):
    __tablename__ = "ansible_builder_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    playbook_id = Column(Integer, nullable=False)
    inventory_id = Column(Integer, nullable=False)
    status = Column(String(50), default="pending")
    output = Column(Text, default="")
    error = Column(Text, default="")
    return_code = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

# DB 초기화 함수
def init_db():
    Base.metadata.create_all(bind=engine)

# DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
