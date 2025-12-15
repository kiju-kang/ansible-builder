from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# PostgreSQL 연결 설정 (Kubernetes AWX PostgreSQL 사용)
# Kubernetes 서비스 이름으로 연결: awx-postgres-15.awx.svc.cluster.local
# 호스트에서 실행 시 kubectl port-forward 필요
# 보안: 비밀번호는 반드시 환경 변수 DATABASE_URL 또는 DB_PASSWORD로 관리해야 함
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://awx:ansiblebuilder@awx-postgres-15.awx.svc.cluster.local:5432/awx"  # Default fallback only for dev
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
    owner_id = Column(Integer, nullable=True)  # User ID
    owner_username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AnsibleBuilderInventory(Base):
    __tablename__ = "ansible_builder_inventories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    owner_id = Column(Integer, nullable=True)  # User ID
    owner_username = Column(String(255), nullable=True)
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

class AnsibleBuilderUser(Base):
    __tablename__ = "ansible_builder_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="user")  # admin, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AnsibleBuilderAuditLog(Base):
    __tablename__ = "ansible_builder_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(255), nullable=True)
    action = Column(String(50), nullable=False)  # CREATE, READ, UPDATE, DELETE, EXECUTE
    resource_type = Column(String(50), nullable=False)  # playbook, inventory, user
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

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
