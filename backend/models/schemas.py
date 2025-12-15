"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel
from typing import List, Dict, Optional


class YamlTextImport(BaseModel):
    """YAML content import model"""
    content: str


class Task(BaseModel):
    """Ansible task model"""
    name: str
    module: str
    params: Dict[str, str]


class Playbook(BaseModel):
    """Playbook model"""
    id: Optional[int] = None
    name: str
    hosts: str
    become: bool
    tasks: List[Task]
    created_at: Optional[str] = None


class Inventory(BaseModel):
    """Inventory model"""
    id: Optional[int] = None
    name: str
    content: str
    created_at: Optional[str] = None


class ExecutionRequest(BaseModel):
    """Execution request model"""
    playbook_id: int
    inventory_id: int
    extra_vars: Optional[Dict[str, str]] = {}


class AWXJobRequest(BaseModel):
    """AWX job request model

    AWX 인증 정보는 환경 변수에서 자동으로 가져옵니다.
    awx_url, awx_token은 선택적으로 제공 가능하며,
    제공하지 않으면 환경 변수(AWX_URL, AWX_TOKEN)를 사용합니다.
    """
    playbook_id: int
    inventory_id: int
    awx_url: Optional[str] = None
    awx_token: Optional[str] = None
    job_template_id: Optional[int] = None
