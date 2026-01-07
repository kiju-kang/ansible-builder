from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Project imports
from models import YamlTextImport, Task, Playbook, Inventory, ExecutionRequest, AWXJobRequest
from utils import resolve_yaml_imports
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import subprocess
import tempfile
import os
import yaml
from datetime import datetime, timedelta
import asyncio
import httpx
import json
import re
import traceback

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Database import
from database import init_db, get_db, AnsibleBuilderPlaybook, AnsibleBuilderInventory, AnsibleBuilderExecution, AnsibleBuilderUser

# Keycloak import (SSO 인증)
from keycloak_auth import get_current_user_keycloak, get_optional_user_keycloak, require_keycloak_user
from keycloak_config import (
    KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID,
    KEYCLOAK_AUTHORIZATION_URL, KEYCLOAK_TOKEN_URL, KEYCLOAK_LOGOUT_URL
)
KEYCLOAK_ENABLED = True
print("✓ Keycloak SSO authentication enabled")

# Ansible 호스트 키 확인 비활성화
os.environ['ANSIBLE_HOST_KEY_CHECKING'] = 'False'

# AWX 통합 설정 (환경 변수에서 로드)
AWX_URL = os.getenv('AWX_URL', 'http://192.168.64.26:30000')
AWX_TOKEN = os.getenv('AWX_TOKEN', '')
AWX_DEFAULT_PROJECT_ID = int(os.getenv('AWX_DEFAULT_PROJECT_ID', '0')) or None  # 기본 프로젝트 ID (0이면 자동 검색)
AWX_DEFAULT_JOB_TEMPLATE_ID = int(os.getenv('AWX_DEFAULT_JOB_TEMPLATE_ID', '0')) or None  # 기본 Job Template ID (0이면 자동 검색)
print(f"✓ AWX integration configured: {AWX_URL}")
if AWX_DEFAULT_PROJECT_ID:
    print(f"  - Default Project ID: {AWX_DEFAULT_PROJECT_ID}")
if AWX_DEFAULT_JOB_TEMPLATE_ID:
    print(f"  - Default Job Template ID: {AWX_DEFAULT_JOB_TEMPLATE_ID}")

app = FastAPI(title="Ansible Playbook Builder API")

# DB 초기화
@app.on_event("startup")
def startup_event():
    init_db()
    print("Database initialized successfully")
    print("User authentication managed by Keycloak SSO")

# CORS 설정 - 모든 오리진 허용 (프로덕션에서는 특정 도메인만 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션: ["https://your-domain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Keycloak SSO 인증
# ============================================
# get_optional_user_keycloak: 인증 선택적 (로그인 없이도 접근 가능)
# require_keycloak_user: 인증 필수 (로그인 필요)
# get_current_user_keycloak: 관리자 권한 필수
# ============================================


# ============================================
# Frontend Configuration API
# ============================================
# Kubernetes ConfigMap에서 환경변수를 읽어 Frontend에 동적으로 제공
# IP 변경 시 ConfigMap만 수정하고 Pod 재시작하면 됨 (빌드 불필요)
# ============================================

@app.get("/api/config")
async def get_frontend_config():
    """
    Frontend에서 사용할 설정값을 환경변수에서 읽어서 반환
    Kubernetes ConfigMap/Secret으로 관리되는 값들
    
    Note: KEYCLOAK_FRONTEND_URL is the external URL for browser access
          KEYCLOAK_SERVER_URL is the internal K8s service URL for backend validation
    """
    # Use external URL for frontend, fallback to KEYCLOAK_SERVER_URL if not set
    keycloak_frontend_url = os.getenv("KEYCLOAK_FRONTEND_URL", KEYCLOAK_SERVER_URL)
    
    return {
        # Keycloak SSO 설정 (external URL for browser)
        "keycloak_url": keycloak_frontend_url,
        "keycloak_realm": KEYCLOAK_REALM,
        "keycloak_client_id": KEYCLOAK_CLIENT_ID,
        
        # AWX 설정
        "awx_url": AWX_URL,
        
        # 앱 설정
        "app_title": os.getenv("APP_TITLE", "Ansible 작업 생성기"),
        "app_env": os.getenv("APP_ENV", "development"),
        
        # Feature flags
        "keycloak_enabled": KEYCLOAK_ENABLED,
    }


# ============================================
# External API Proxy (CORS 우회)
# ============================================

@app.post("/api/proxy/inventory/list")
async def proxy_inventory_list():
    """
    외부 API(10.2.14.54:8081) CORS 우회를 위한 프록시 엔드포인트
    Frontend에서 직접 외부 API 호출 시 CORS 에러 발생하므로 Backend를 경유
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://10.2.14.54:8081/ext/api/inventory/list",
                json={},
                headers={"Content-Type": "application/json"}
            )
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="External API request timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"External API connection failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")


# Playbook CRUD (DB 사용)
def log_action(db, user, action, resource_type, resource_id, description, ip_address=None):
    """Audit logging stub - logs actions to console"""
    user_info = user.username if user else "anonymous"
    print(f"[AUDIT] {action} {resource_type}#{resource_id} by {user_info}: {description}")

def validate_task_params(tasks: List[Task]) -> dict:
    """
    Validate task parameters to detect issues that would fail in AWX executor.
    Returns a dict with 'valid' boolean and 'warnings' list.
    """
    warnings = []

    for idx, task in enumerate(tasks, 1):
        # Check for nested loop patterns ({{ item }} in params)
        for param_key, param_value in task.params.items():
            if isinstance(param_value, str) and '{{ item }}' in param_value:
                warnings.append({
                    "task_index": idx,
                    "task_name": task.name,
                    "issue": "nested_loop",
                    "message": f"Task #{idx} '{task.name}' uses '{{{{ item }}}}' in params.{param_key}. "
                               f"This will not work in AWX executor. "
                               f"Please split into separate tasks or use shell/command module with explicit values."
                })

    return {
        "valid": len(warnings) == 0,
        "warnings": warnings
    }

def validate_yaml_content(content: str) -> dict:
    """
    Validate YAML content syntax.
    Returns a dict with 'valid' boolean, 'error' message, and 'line' number if invalid.
    """
    try:
        yaml.safe_load(content)
        return {
            "valid": True,
            "error": None,
            "line": None
        }
    except yaml.YAMLError as e:
        error_msg = str(e)
        line_num = None

        # Extract line number from error message if available
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            line_num = mark.line + 1  # YAML uses 0-based indexing
            column = mark.column + 1
            error_msg = f"YAML syntax error at line {line_num}, column {column}: {e.problem}"

        return {
            "valid": False,
            "error": error_msg,
            "line": line_num
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"YAML parsing error: {str(e)}",
            "line": None
        }

def validate_script_content(content: str) -> dict:
    """
    Validate shell script content syntax using bash -n (dry-run).
    Returns a dict with 'valid' boolean, 'error' message, and 'line' number if invalid.
    """
    try:
        # Check for empty content
        if not content.strip():
            return {
                "valid": False,
                "error": "Script content is empty",
                "line": None
            }

        # Use bash -n to check syntax without executing
        result = subprocess.run(
            ['bash', '-n'],
            input=content.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )

        if result.returncode == 0:
            return {
                "valid": True,
                "error": None,
                "line": None
            }
        else:
            error_msg = result.stderr.decode('utf-8').strip()
            line_num = None

            # Extract line number from bash error message
            # Format: "bash: line X: ..."
            line_match = re.search(r'line (\d+):', error_msg)
            if line_match:
                line_num = int(line_match.group(1))

            return {
                "valid": False,
                "error": error_msg or "Shell script syntax error",
                "line": line_num
            }
    except subprocess.TimeoutExpired:
        return {
            "valid": False,
            "error": "Script validation timeout (syntax check took too long)",
            "line": None
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Script validation error: {str(e)}",
            "line": None
        }

@app.post("/api/playbooks", response_model=Playbook)
async def create_playbook(
    playbook: Playbook,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
):
    # Validate task parameters
    validation = validate_task_params(playbook.tasks)
    if not validation['valid']:
        # Log warnings but allow creation
        print(f"⚠️ Playbook '{playbook.name}' has validation warnings:")
        for warning in validation['warnings']:
            print(f"  - Task #{warning['task_index']}: {warning['message']}")

    db_playbook = AnsibleBuilderPlaybook(
        name=playbook.name,
        hosts=playbook.hosts,
        become=playbook.become,
        tasks=json.dumps([task.dict() for task in playbook.tasks]),
        owner_id=current_user.id if current_user else None,
        owner_username=current_user.username if current_user else None
    )
    db.add(db_playbook)
    db.commit()
    db.refresh(db_playbook)

    # 감사 로그
    log_action(db, current_user, "CREATE", "playbook", db_playbook.id,
               f"Created playbook: {playbook.name}", request.client.host if request.client else None)

    return Playbook(
        id=db_playbook.id,
        name=db_playbook.name,
        hosts=db_playbook.hosts,
        become=db_playbook.become,
        tasks=[Task(**task) for task in json.loads(db_playbook.tasks)],
        created_at=db_playbook.created_at.isoformat()
    )

@app.get("/api/playbooks", response_model=List[Playbook])
async def list_playbooks(db: Session = Depends(get_db)):
    playbooks = db.query(AnsibleBuilderPlaybook).all()
    return [
        Playbook(
            id=pb.id,
            name=pb.name,
            hosts=pb.hosts,
            become=pb.become,
            tasks=[Task(**task) for task in json.loads(pb.tasks)],
            created_at=pb.created_at.isoformat()
        )
        for pb in playbooks
    ]

@app.get("/api/playbooks/{playbook_id}", response_model=Playbook)
async def get_playbook(playbook_id: int, db: Session = Depends(get_db)):
    pb = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == playbook_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    return Playbook(
        id=pb.id,
        name=pb.name,
        hosts=pb.hosts,
        become=pb.become,
        tasks=[Task(**task) for task in json.loads(pb.tasks)],
        created_at=pb.created_at.isoformat()
    )

@app.put("/api/playbooks/{playbook_id}", response_model=Playbook)
async def update_playbook(
    playbook_id: int,
    playbook: Playbook,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
):
    db_playbook = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == playbook_id).first()
    if not db_playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    # 권한 체크
    if current_user and not check_resource_access(current_user, db_playbook.owner_id):
        raise HTTPException(status_code=403, detail="Not authorized to update this playbook")

    db_playbook.name = playbook.name
    db_playbook.hosts = playbook.hosts
    db_playbook.become = playbook.become
    db_playbook.tasks = json.dumps([task.dict() for task in playbook.tasks])
    db_playbook.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_playbook)

    # 감사 로그
    log_action(db, current_user, "UPDATE", "playbook", playbook_id,
               f"Updated playbook: {playbook.name}", request.client.host if request.client else None)

    return Playbook(
        id=db_playbook.id,
        name=db_playbook.name,
        hosts=db_playbook.hosts,
        become=db_playbook.become,
        tasks=[Task(**task) for task in json.loads(db_playbook.tasks)],
        created_at=db_playbook.created_at.isoformat()
    )

@app.delete("/api/playbooks/{playbook_id}")
async def delete_playbook(
    playbook_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
):
    db_playbook = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == playbook_id).first()
    if not db_playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    # 권한 체크
    if current_user and not check_resource_access(current_user, db_playbook.owner_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this playbook")

    playbook_name = db_playbook.name
    db.delete(db_playbook)
    db.commit()

    # 감사 로그
    log_action(db, current_user, "DELETE", "playbook", playbook_id,
               f"Deleted playbook: {playbook_name}", request.client.host if request.client else None)

    return {"message": "Playbook deleted"}

# Inventory CRUD (DB 사용)
@app.post("/api/inventories", response_model=Inventory)
async def create_inventory(
    inventory: Inventory,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
):
    db_inventory = AnsibleBuilderInventory(
        name=inventory.name,
        content=inventory.content,
        owner_id=current_user.id if current_user else None,
        owner_username=current_user.username if current_user else None
    )
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)

    # 감사 로그
    log_action(db, current_user, "CREATE", "inventory", db_inventory.id,
               f"Created inventory: {inventory.name}", request.client.host if request.client else None)

    return Inventory(
        id=db_inventory.id,
        name=db_inventory.name,
        content=db_inventory.content,
        created_at=db_inventory.created_at.isoformat()
    )

@app.get("/api/inventories", response_model=List[Inventory])
async def list_inventories(db: Session = Depends(get_db)):
    inventories = db.query(AnsibleBuilderInventory).all()
    return [
        Inventory(
            id=inv.id,
            name=inv.name,
            content=inv.content,
            created_at=inv.created_at.isoformat()
        )
        for inv in inventories
    ]

@app.get("/api/inventories/{inventory_id}", response_model=Inventory)
async def get_inventory(inventory_id: int, db: Session = Depends(get_db)):
    inv = db.query(AnsibleBuilderInventory).filter(AnsibleBuilderInventory.id == inventory_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    return Inventory(
        id=inv.id,
        name=inv.name,
        content=inv.content,
        created_at=inv.created_at.isoformat()
    )

@app.delete("/api/inventories/{inventory_id}")
async def delete_inventory(
    inventory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
):
    db_inventory = db.query(AnsibleBuilderInventory).filter(AnsibleBuilderInventory.id == inventory_id).first()
    if not db_inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    # 권한 체크
    if current_user and not check_resource_access(current_user, db_inventory.owner_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this inventory")

    inventory_name = db_inventory.name
    db.delete(db_inventory)
    db.commit()

    # 감사 로그
    log_action(db, current_user, "DELETE", "inventory", inventory_id,
               f"Deleted inventory: {inventory_name}", request.client.host if request.client else None)

    return {"message": "Inventory deleted"}

# YAML Import 기능
@app.post("/api/playbooks/import")
async def import_playbook_from_yaml(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """YAML 파일을 업로드하여 Playbook 자동 생성"""
    try:
        # 파일 읽기
        content = await file.read()
        yaml_content = content.decode('utf-8')

        # YAML 구문 검사
        validation = validate_yaml_content(yaml_content)
        if not validation['valid']:
            line_info = f" (line {validation['line']})" if validation['line'] else ""
            error_msg = f"YAML syntax error{line_info}: {validation['error']}"
            raise HTTPException(status_code=400, detail=error_msg)

        # Resolve custom 'import:' statements
        base_dir = "/root/ansible-builder/ansible-builder/backend/playbooks"
        resolved_yaml = resolve_yaml_imports(yaml_content, base_dir)

        # YAML 파싱
        parsed_yaml = yaml.safe_load(resolved_yaml)
        
        # YAML이 리스트인 경우 (다중 play)
        if isinstance(parsed_yaml, list):
            if not parsed_yaml:
                raise HTTPException(status_code=400, detail="Empty YAML file")
            
            # 모든 play의 task를 수집
            all_tasks = []
            playbook_name = None
            hosts = "all"
            become = False
            
            for play in parsed_yaml:
                if not isinstance(play, dict):
                    continue
                
                # 첫 번째 play의 메타데이터 사용
                if not playbook_name:
                    playbook_name = play.get('name', f'Imported Playbook - {datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
                    hosts = play.get('hosts', 'all')
                    become = play.get('become', False)
                
                # tasks 키가 있으면 수집
                tasks_data = play.get('tasks', [])
                for task in tasks_data:
                    if isinstance(task, dict):
                        all_tasks.append(task)
                
                # roles 키가 있으면 각 role을 task로 변환
                roles_data = play.get('roles', [])
                if roles_data:
                    for role in roles_data:
                        if isinstance(role, str):
                            # 단순 문자열 role
                            all_tasks.append({
                                'name': f'Execute role: {role}',
                                'include_role': {'name': role}
                            })
                        elif isinstance(role, dict):
                            # dict 형태의 role
                            role_name = role.get('role') or role.get('name', 'unknown')
                            all_tasks.append({
                                'name': f'Execute role: {role_name}',
                                'include_role': role
                            })
            
            tasks_data = all_tasks
        else:
            # 단일 play
            play = parsed_yaml
            playbook_name = play.get('name', f'Imported Playbook - {datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
            hosts = play.get('hosts', 'all')
            become = play.get('become', False)
            
            # tasks와 roles 모두 수집
            tasks_data = play.get('tasks', [])
            
            # roles가 있으면 tasks로 변환
            roles_data = play.get('roles', [])
            if roles_data:
                role_tasks = []
                for role in roles_data:
                    if isinstance(role, str):
                        role_tasks.append({
                            'name': f'Execute role: {role}',
                            'include_role': {'name': role}
                        })
                    elif isinstance(role, dict):
                        role_name = role.get('role') or role.get('name', 'unknown')
                        role_tasks.append({
                            'name': f'Execute role: {role_name}',
                            'include_role': role
                        })
                # roles를 tasks 앞에 추가
                tasks_data = role_tasks + tasks_data
        
        # Task 변환
        converted_tasks = []
        excluded_keys = ['name', 'become', 'when', 'register', 'ignore_errors', 
                       'tags', 'with_items', 'loop', 'until', 'retries', 'delay',
                       'changed_when', 'failed_when', 'notify', 'vars', 'environment',
                       'delegate_to', 'run_once', 'async', 'poll', 'block', 'rescue', 'always']
        
        for task in tasks_data:
            if not isinstance(task, dict):
                continue
            
            task_name = task.get('name', 'Unnamed task')
            
            # 모듈 찾기
            module_name = None
            module_params = {}
            
            for key, value in task.items():
                if key not in excluded_keys:
                    module_name = key
                    
                    # ansible.builtin.xxx 형태 처리
                    if '.' in module_name:
                        module_name = module_name.split('.')[-1]
                    
                    if isinstance(value, dict):
                        module_params = value
                    elif isinstance(value, str):
                        if module_name in ['command', 'shell']:
                            module_params = {'cmd': value}
                        elif module_name in ['apt', 'yum', 'package']:
                            module_params = {'name': value, 'state': 'present'}
                        elif module_name in ['copy', 'template']:
                            module_params = {'src': '', 'dest': value}
                        elif module_name in ['include_role']:
                            module_params = {'name': value}
                        else:
                            module_params = {'name': value}
                    elif isinstance(value, list):
                        module_params = {'items': ', '.join(str(v) for v in value)}
                    else:
                        module_params = {'value': str(value)}
                    break
            
            if module_name:
                params_dict = {}
                for k, v in module_params.items():
                    if isinstance(v, (list, dict)):
                        params_dict[k] = json.dumps(v) if isinstance(v, dict) else str(v)
                    else:
                        params_dict[k] = str(v) if v is not None else ""
                
                converted_task = {
                    'name': task_name,
                    'module': module_name,
                    'params': params_dict
                }
                
                # loop/with_items 속성 보존
                if task.get('loop'):
                    converted_task['loop'] = task.get('loop')
                elif task.get('with_items'):
                    converted_task['loop'] = task.get('with_items')
                
                # 모든 Ansible Task 속성 보존
                task_attrs = [
                    'become', 'when', 'delegate_to', 'register', 
                    'ignore_errors', 'failed_when', 'changed_when',
                    'run_once', 'retries', 'until', 'delay',
                    'notify', 'tags', 'environment', 'vars',
                    'async', 'poll', 'no_log', 'loop_control'
                ]
                
                for attr in task_attrs:
                    if task.get(attr) is not None:
                        converted_task[attr] = task.get(attr)
                
                converted_tasks.append(converted_task)
        
        if not converted_tasks:
            raise HTTPException(status_code=400, detail="No valid tasks found in YAML")
        
        # DB에 저장
        db_playbook = AnsibleBuilderPlaybook(
            name=playbook_name,
            hosts=hosts,
            become=become,
            tasks=json.dumps(converted_tasks)
        )
        db.add(db_playbook)
        db.commit()
        db.refresh(db_playbook)

        return {
            "status": "success",
            "playbook_id": db_playbook.id,
            "playbook_name": playbook_name,
            "tasks_count": len(converted_tasks),
            "message": f"Successfully imported playbook with {len(converted_tasks)} tasks",
            "playbook": {
                "id": db_playbook.id,
                "name": playbook_name,
                "hosts": hosts,
                "become": become,
                "tasks": converted_tasks
            }
        }
        
    except HTTPException:
        # Re-raise HTTPException as is (from validation)
        raise
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")
    except Exception as e:
        error_detail = f"Import failed: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@app.post("/api/playbooks/import-text")
async def import_playbook_from_text(data: YamlTextImport, db: Session = Depends(get_db)):
    """YAML 텍스트를 직접 입력하여 Playbook 자동 생성"""
    try:
        yaml_text = data.content

        # YAML 구문 검사
        validation = validate_yaml_content(yaml_text)
        if not validation['valid']:
            line_info = f" (line {validation['line']})" if validation['line'] else ""
            error_msg = f"YAML syntax error{line_info}: {validation['error']}"
            raise HTTPException(status_code=400, detail=error_msg)

        # Resolve custom 'import:' statements
        base_dir = "/root/ansible-builder/ansible-builder/backend/playbooks"
        resolved_yaml = resolve_yaml_imports(yaml_text, base_dir)

        # YAML 파싱
        parsed_yaml = yaml.safe_load(resolved_yaml)
        
        # YAML이 리스트인 경우 첫 번째 play 사용
        if isinstance(parsed_yaml, list):
            if not parsed_yaml:
                raise HTTPException(status_code=400, detail="Empty YAML content")
            play = parsed_yaml[0]
        else:
            play = parsed_yaml
        
        # Playbook 정보 추출
        playbook_name = play.get('name', f'Imported Playbook - {datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
        hosts = play.get('hosts', 'all')
        become = play.get('become', False)
        tasks_data = play.get('tasks', [])
        
        # Task 변환
        converted_tasks = []
        for task in tasks_data:
            if not isinstance(task, dict):
                continue
            
            task_name = task.get('name', 'Unnamed task')
            
            # 모듈 찾기
            module_name = None
            module_params = {}
            
            for key, value in task.items():
                if key not in ['name', 'become', 'when', 'register', 'ignore_errors', 'tags']:
                    module_name = key
                    if isinstance(value, dict):
                        module_params = value
                    elif isinstance(value, str):
                        module_params = {'cmd': value} if module_name in ['command', 'shell'] else {'name': value}
                    break
            
            if module_name:
                params_dict = {}
                for k, v in module_params.items():
                    params_dict[k] = str(v) if v is not None else ""
                
                converted_task = {
                    'name': task_name,
                    'module': module_name,
                    'params': params_dict
                }
                
                # loop/with_items 속성 보존
                if task.get('loop'):
                    converted_task['loop'] = task.get('loop')
                elif task.get('with_items'):
                    converted_task['loop'] = task.get('with_items')
                
                # 모든 Ansible Task 속성 보존
                task_attrs = [
                    'become', 'when', 'delegate_to', 'register', 
                    'ignore_errors', 'failed_when', 'changed_when',
                    'run_once', 'retries', 'until', 'delay',
                    'notify', 'tags', 'environment', 'vars',
                    'async', 'poll', 'no_log', 'loop_control'
                ]
                
                for attr in task_attrs:
                    if task.get(attr) is not None:
                        converted_task[attr] = task.get(attr)
                
                converted_tasks.append(converted_task)
        
        # DB에 저장
        db_playbook = AnsibleBuilderPlaybook(
            name=playbook_name,
            hosts=hosts,
            become=become,
            tasks=json.dumps(converted_tasks)
        )
        db.add(db_playbook)
        db.commit()
        db.refresh(db_playbook)

        return {
            "status": "success",
            "playbook_id": db_playbook.id,
            "playbook_name": playbook_name,
            "tasks_count": len(converted_tasks),
            "message": f"Successfully imported playbook with {len(converted_tasks)} tasks",
            "playbook": {
                "id": db_playbook.id,
                "name": playbook_name,
                "hosts": hosts,
                "become": become,
                "tasks": converted_tasks
            }
        }

    except HTTPException:
        # Re-raise HTTPException as is (from validation)
        raise
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


# ============================================
# Syntax Validation Endpoints
# ============================================

class YamlValidationRequest(BaseModel):
    content: str

class ScriptValidationRequest(BaseModel):
    content: str

@app.post("/api/playbooks/validate-yaml")
async def validate_yaml_syntax(data: YamlValidationRequest):
    """YAML 문법 검사 (import 없이 검증만)"""
    try:
        content = data.content.strip()
        if not content:
            return {
                "valid": False,
                "error": "Empty YAML content",
                "line": None,
                "column": None
            }
        
        # YAML 파싱 시도
        parsed = yaml.safe_load(content)
        
        # Ansible Playbook 구조 검증
        if parsed is None:
            return {
                "valid": False,
                "error": "YAML content is empty or contains only comments",
                "line": None,
                "column": None
            }
        
        # 리스트 형태의 playbook인지 확인
        if isinstance(parsed, list):
            if not parsed:
                return {
                    "valid": False,
                    "error": "Empty playbook list",
                    "line": None,
                    "column": None
                }
            
            # 각 play가 dict인지 확인
            for idx, play in enumerate(parsed):
                if not isinstance(play, dict):
                    return {
                        "valid": False,
                        "error": f"Play #{idx + 1} is not a valid dictionary",
                        "line": None,
                        "column": None
                    }
                
                # 최소한 hosts 또는 tasks가 있어야 함
                if 'hosts' not in play and 'tasks' not in play and 'roles' not in play and 'name' not in play:
                    return {
                        "valid": False,
                        "error": f"Play #{idx + 1} is missing required keys (hosts, tasks, roles, or name)",
                        "line": None,
                        "column": None
                    }
        elif isinstance(parsed, dict):
            # 단일 play도 허용
            if 'hosts' not in parsed and 'tasks' not in parsed and 'roles' not in parsed and 'name' not in parsed:
                return {
                    "valid": False,
                    "error": "Playbook is missing required keys (hosts, tasks, roles, or name)",
                    "line": None,
                    "column": None
                }
        else:
            return {
                "valid": False,
                "error": f"Invalid playbook structure. Expected list or dictionary, got {type(parsed).__name__}",
                "line": None,
                "column": None
            }
        
        # 모든 검사 통과
        tasks_count = 0
        if isinstance(parsed, list):
            for play in parsed:
                if isinstance(play, dict):
                    tasks_count += len(play.get('tasks', []))
                    tasks_count += len(play.get('roles', []))
        elif isinstance(parsed, dict):
            tasks_count = len(parsed.get('tasks', [])) + len(parsed.get('roles', []))
        
        return {
            "valid": True,
            "message": f"Valid Ansible playbook syntax. Found {tasks_count} tasks/roles.",
            "tasks_count": tasks_count
        }
        
    except yaml.YAMLError as e:
        # YAML 파싱 에러에서 줄 번호 추출
        error_msg = str(e)
        line = None
        column = None
        
        if hasattr(e, 'problem_mark') and e.problem_mark:
            line = e.problem_mark.line + 1
            column = e.problem_mark.column + 1
            error_msg = f"{e.problem}" if hasattr(e, 'problem') else str(e)
        
        return {
            "valid": False,
            "error": f"YAML syntax error: {error_msg}",
            "line": line,
            "column": column
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Validation failed: {str(e)}",
            "line": None,
            "column": None
        }


@app.post("/api/playbooks/validate-script")
async def validate_script_syntax(data: ScriptValidationRequest):
    """Shell 스크립트 문법 검사 (bash -n 사용)"""
    try:
        content = data.content.strip()
        if not content:
            return {
                "valid": False,
                "error": "Empty script content",
                "line": None
            }
        
        # 임시 파일에 스크립트 저장
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # bash -n으로 문법 검사 (실행하지 않고 검사만)
            result = subprocess.run(
                ['bash', '-n', temp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # 스크립트 통계 수집
                lines = content.split('\n')
                command_count = sum(1 for line in lines 
                                   if line.strip() and not line.strip().startswith('#'))
                
                return {
                    "valid": True,
                    "message": f"Valid shell script syntax. Found {command_count} commands.",
                    "command_count": command_count
                }
            else:
                # 에러 메시지 파싱
                error_output = result.stderr or result.stdout
                line = None
                
                # bash 에러 메시지에서 줄 번호 추출 시도
                # 예: "script.sh: line 5: syntax error..."
                import re
                line_match = re.search(r'line (\d+):', error_output)
                if line_match:
                    line = int(line_match.group(1))
                
                return {
                    "valid": False,
                    "error": error_output.strip() or "Unknown syntax error",
                    "line": line
                }
                
        finally:
            # 임시 파일 삭제
            os.unlink(temp_path)
            
    except subprocess.TimeoutExpired:
        return {
            "valid": False,
            "error": "Script validation timed out",
            "line": None
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Validation failed: {str(e)}",
            "line": None
        }

# import script

@app.post("/api/playbooks/import-script")
async def import_script_as_playbook(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """셸 스크립트(.sh, .bash) 파일을 Playbook으로 변환"""
    try:
        content = await file.read()
        script_content = content.decode('utf-8')

        if not script_content.strip():
            raise HTTPException(status_code=400, detail="Empty script file")

        # 스크립트 구문 검사
        validation = validate_script_content(script_content)
        if not validation['valid']:
            line_info = f" (line {validation['line']})" if validation['line'] else ""
            error_msg = f"Shell script syntax error{line_info}: {validation['error']}"
            raise HTTPException(status_code=400, detail=error_msg)

        # 파일명에서 playbook 이름 생성
        script_name = file.filename.replace('.sh', '').replace('.bash', '').replace('.zsh', '')
        playbook_name = f"Script_{script_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # 스크립트를 분석하여 tasks 생성
        tasks = []
        lines = script_content.split('\n')
        
        # 전체 스크립트를 하나의 shell task로 변환하는 간단한 방식
        # 또는 라인별로 분석하여 개별 task로 분리
        
        # 방법 1: 전체 스크립트를 하나의 task로
        tasks.append({
            "name": f"Execute {script_name} script",
            "module": "shell",
            "params": {
                "cmd": script_content,
                "executable": "/bin/bash"
            }
        })
        
        # 방법 2: 스크립트를 분석하여 의미있는 task로 분리
        current_block = []
        block_name = "Initial setup"
        
        for line in lines:
            stripped = line.strip()
            
            # 빈 줄이나 주석은 블록 구분자로 사용
            if not stripped or stripped.startswith('#'):
                if current_block and not stripped.startswith('#!'):
                    # 현재 블록을 task로 추가
                    if len(current_block) > 0:
                        tasks.append({
                            "name": block_name,
                            "module": "shell",
                            "params": {
                                "cmd": '\n'.join(current_block),
                                "executable": "/bin/bash"
                            }
                        })
                    current_block = []
                    
                # 주석에서 task 이름 추출
                if stripped.startswith('#') and not stripped.startswith('#!'):
                    block_name = stripped.lstrip('#').strip() or "Execute commands"
                continue
            
            # apt/yum install 명령 감지
            if 'apt-get install' in stripped or 'apt install' in stripped:
                packages = []
                for word in stripped.split():
                    if word not in ['apt-get', 'apt', 'install', 'sudo', '-y', '--yes']:
                        packages.append(word)
                
                if packages:
                    tasks.append({
                        "name": f"Install packages: {', '.join(packages)}",
                        "module": "apt",
                        "params": {
                            "name": ','.join(packages),
                            "state": "present",
                            "update_cache": "yes"
                        }
                    })
                    continue
            
            if 'yum install' in stripped:
                packages = []
                for word in stripped.split():
                    if word not in ['yum', 'install', 'sudo', '-y']:
                        packages.append(word)
                
                if packages:
                    tasks.append({
                        "name": f"Install packages: {', '.join(packages)}",
                        "module": "yum",
                        "params": {
                            "name": ','.join(packages),
                            "state": "present"
                        }
                    })
                    continue
            
            # systemctl 명령 감지
            if 'systemctl' in stripped:
                parts = stripped.split()
                if 'start' in parts:
                    service_idx = parts.index('start') + 1
                    if service_idx < len(parts):
                        tasks.append({
                            "name": f"Start service {parts[service_idx]}",
                            "module": "service",
                            "params": {
                                "name": parts[service_idx],
                                "state": "started"
                            }
                        })
                        continue
                elif 'enable' in parts:
                    service_idx = parts.index('enable') + 1
                    if service_idx < len(parts):
                        tasks.append({
                            "name": f"Enable service {parts[service_idx]}",
                            "module": "service",
                            "params": {
                                "name": parts[service_idx],
                                "enabled": "yes"
                            }
                        })
                        continue
            
            # mkdir 명령 감지
            if stripped.startswith('mkdir'):
                parts = stripped.split()
                if len(parts) >= 2:
                    path = parts[-1]
                    tasks.append({
                        "name": f"Create directory {path}",
                        "module": "file",
                        "params": {
                            "path": path,
                            "state": "directory",
                            "mode": "0755"
                        }
                    })
                    continue
            
            # 일반 명령은 블록에 추가
            current_block.append(line)
        
        # 마지막 블록 처리
        if current_block:
            tasks.append({
                "name": block_name,
                "module": "shell",
                "params": {
                    "cmd": '\n'.join(current_block),
                    "executable": "/bin/bash"
                }
            })
        
        # tasks가 없으면 전체 스크립트를 하나의 task로
        if not tasks:
            tasks.append({
                "name": f"Execute {script_name}",
                "module": "shell",
                "params": {
                    "cmd": script_content,
                    "executable": "/bin/bash"
                }
            })
        
        # DB에 저장
        db_playbook = AnsibleBuilderPlaybook(
            name=playbook_name,
            hosts="all",
            become=True,  # 스크립트는 보통 sudo 권한 필요
            tasks=json.dumps(tasks)
        )
        db.add(db_playbook)
        db.commit()
        db.refresh(db_playbook)

        return {
            "status": "success",
            "playbook_id": db_playbook.id,
            "playbook_name": playbook_name,
            "tasks_count": len(tasks),
            "message": f"Successfully converted script to playbook with {len(tasks)} tasks",
            "playbook": {
                "id": db_playbook.id,
                "name": playbook_name,
                "hosts": "all",
                "become": True,
                "tasks": tasks
            }
        }
        
    except HTTPException:
        # Re-raise HTTPException as is (from validation)
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8")
    except Exception as e:
        error_detail = f"Import failed: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.post("/api/playbooks/import-script-text")
async def import_script_text_as_playbook(data: dict, db: Session = Depends(get_db)):
    """스크립트 텍스트를 직접 입력하여 Playbook 생성"""
    try:
        script_text = data.get('content', '')
        playbook_name = data.get('name', f'Script_Playbook_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')

        if not script_text.strip():
            raise HTTPException(status_code=400, detail="Empty script content")

        # 스크립트 구문 검사
        validation = validate_script_content(script_text)
        if not validation['valid']:
            line_info = f" (line {validation['line']})" if validation['line'] else ""
            error_msg = f"Shell script syntax error{line_info}: {validation['error']}"
            raise HTTPException(status_code=400, detail=error_msg)

        # 스크립트 분석 및 task 생성 (위와 동일한 로직)
        tasks = []
        lines = script_text.split('\n')
        
        current_block = []
        block_name = "Execute script commands"
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped or stripped.startswith('#'):
                if current_block and not stripped.startswith('#!'):
                    if len(current_block) > 0:
                        tasks.append({
                            "name": block_name,
                            "module": "shell",
                            "params": {
                                "cmd": '\n'.join(current_block),
                                "executable": "/bin/bash"
                            }
                        })
                    current_block = []
                
                if stripped.startswith('#') and not stripped.startswith('#!'):
                    block_name = stripped.lstrip('#').strip() or "Execute commands"
                continue
            
            # 패키지 설치 명령 감지
            if 'apt-get install' in stripped or 'apt install' in stripped:
                packages = [w for w in stripped.split() 
                           if w not in ['apt-get', 'apt', 'install', 'sudo', '-y', '--yes']]
                if packages:
                    tasks.append({
                        "name": f"Install packages: {', '.join(packages)}",
                        "module": "apt",
                        "params": {
                            "name": ','.join(packages),
                            "state": "present",
                            "update_cache": "yes"
                        }
                    })
                    continue
            
            if 'yum install' in stripped:
                packages = [w for w in stripped.split() 
                           if w not in ['yum', 'install', 'sudo', '-y']]
                if packages:
                    tasks.append({
                        "name": f"Install packages: {', '.join(packages)}",
                        "module": "yum",
                        "params": {
                            "name": ','.join(packages),
                            "state": "present"
                        }
                    })
                    continue
            
            # systemctl 명령 처리
            if 'systemctl' in stripped:
                parts = stripped.split()
                if 'start' in parts:
                    service_idx = parts.index('start') + 1
                    if service_idx < len(parts):
                        tasks.append({
                            "name": f"Start service {parts[service_idx]}",
                            "module": "service",
                            "params": {
                                "name": parts[service_idx],
                                "state": "started"
                            }
                        })
                        continue
                elif 'enable' in parts:
                    service_idx = parts.index('enable') + 1
                    if service_idx < len(parts):
                        tasks.append({
                            "name": f"Enable service {parts[service_idx]}",
                            "module": "service",
                            "params": {
                                "name": parts[service_idx],
                                "enabled": "yes"
                            }
                        })
                        continue
            
            # mkdir 명령
            if stripped.startswith('mkdir'):
                parts = stripped.split()
                if len(parts) >= 2:
                    path = parts[-1]
                    tasks.append({
                        "name": f"Create directory {path}",
                        "module": "file",
                        "params": {
                            "path": path,
                            "state": "directory",
                            "mode": "0755"
                        }
                    })
                    continue
            
            current_block.append(line)
        
        # 마지막 블록 처리
        if current_block:
            tasks.append({
                "name": block_name,
                "module": "shell",
                "params": {
                    "cmd": '\n'.join(current_block),
                    "executable": "/bin/bash"
                }
            })
        
        # tasks가 없으면 전체를 하나의 task로
        if not tasks:
            tasks.append({
                "name": "Execute script",
                "module": "shell",
                "params": {
                    "cmd": script_text,
                    "executable": "/bin/bash"
                }
            })
        
        # DB에 저장
        db_playbook = AnsibleBuilderPlaybook(
            name=playbook_name,
            hosts="all",
            become=True,
            tasks=json.dumps(tasks)
        )
        db.add(db_playbook)
        db.commit()
        db.refresh(db_playbook)

        return {
            "status": "success",
            "playbook_id": db_playbook.id,
            "playbook_name": playbook_name,
            "tasks_count": len(tasks),
            "message": f"Successfully converted script to playbook with {len(tasks)} tasks",
            "playbook": {
                "id": db_playbook.id,
                "name": playbook_name,
                "hosts": "all",
                "become": True,
                "tasks": tasks
            }
        }

    except HTTPException:
        # Re-raise HTTPException as is (from validation)
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


# Playbook 실행
def generate_yaml(playbook: dict) -> str:
    yaml_content = {
        "name": playbook["name"],
        "hosts": playbook["hosts"],
        "tasks": []
    }
    
    if playbook["become"]:
        yaml_content["become"] = True
    
    for task in playbook["tasks"]:
        task_dict = {
            "name": task["name"],
            task["module" ]: {k: v for k, v in task["params"].items() if v}
        }
        yaml_content["tasks"].append(task_dict)
    
    return yaml.dump([yaml_content], default_flow_style=False)

async def run_ansible_playbook(exec_id: int, playbook_content: str, inventory_content: str, extra_vars: dict, db: Session):
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as pb_file:
            pb_file.write(playbook_content)
            playbook_path = pb_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as inv_file:
            inv_file.write(inventory_content)
            inventory_path = inv_file.name
        
        cmd = [
            "ansible-playbook",
            "-i", inventory_path,
            playbook_path,
            "-c", "local"
        ]
        
        if extra_vars:
            extra_vars_str = " ".join([f"{k}={v}" for k, v in extra_vars.items()])
            cmd.extend(["-e", extra_vars_str])
        
        execution = db.query(AnsibleBuilderExecution).filter(AnsibleBuilderExecution.id == exec_id).first()
        execution.status = "running"
        execution.output = ""
        db.commit()
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # 실시간 출력 수집
        output = ""
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded_line = line.decode()
            output += decoded_line
            execution.output = output
            db.commit()
        
        await process.wait()
        
        execution.status = "completed" if process.returncode == 0 else "failed"
        execution.return_code = process.returncode
        execution.ended_at = datetime.utcnow()
        db.commit()
        
        os.unlink(playbook_path)
        os.unlink(inventory_path)
        
    except Exception as e:
        execution = db.query(AnsibleBuilderExecution).filter(AnsibleBuilderExecution.id == exec_id).first()
        execution.status = "error"
        execution.error = str(e)
        execution.ended_at = datetime.utcnow()
        db.commit()

@app.post("/api/execute")
async def execute_playbook(request: ExecutionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    playbook = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == request.playbook_id).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    inventory = db.query(AnsibleBuilderInventory).filter(AnsibleBuilderInventory.id == request.inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    
    playbook_yaml = generate_yaml(playbook_dict)
    
    execution = AnsibleBuilderExecution(
        playbook_id=request.playbook_id,
        inventory_id=request.inventory_id,
        status="pending"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    background_tasks.add_task(
        run_ansible_playbook,
        execution.id,
        playbook_yaml,
        inventory.content,
        request.extra_vars,
        db
    )
    
    return {"execution_id": execution.id, "status": "pending"}

@app.get("/api/executions/{exec_id}")
async def get_execution_status(exec_id: int, db: Session = Depends(get_db)):
    execution = db.query(AnsibleBuilderExecution).filter(AnsibleBuilderExecution.id == exec_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {
        "id": execution.id,
        "playbook_id": execution.playbook_id,
        "inventory_id": execution.inventory_id,
        "status": execution.status,
        "output": execution.output,
        "error": execution.error,
        "return_code": execution.return_code,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "ended_at": execution.ended_at.isoformat() if execution.ended_at else None
    }

@app.get("/api/executions")
async def list_executions(db: Session = Depends(get_db)):
    executions = db.query(AnsibleBuilderExecution).order_by(AnsibleBuilderExecution.started_at.desc()).all()
    return [
        {
            "id": ex.id,
            "playbook_id": ex.playbook_id,
            "inventory_id": ex.inventory_id,
            "status": ex.status,
            "output": ex.output,
            "error": ex.error,
            "return_code": ex.return_code,
            "started_at": ex.started_at.isoformat() if ex.started_at else None,
            "ended_at": ex.ended_at.isoformat() if ex.ended_at else None
        }
        for ex in executions
    ]

@app.post("/api/playbooks/{playbook_id}/yaml")
async def generate_playbook_yaml(playbook_id: int, db: Session = Depends(get_db)):
    playbook = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == playbook_id).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    yaml_content = generate_yaml(playbook_dict)
    
    return {"yaml": yaml_content}

@app.get("/api")
async def api_root():
    return {
        "message": "Ansible Playbook Builder API",
        "version": "1.0.0",
        "endpoints": {
            "playbooks": "/api/playbooks",
            "inventories": "/api/inventories",
            "execute": "/api/execute",
            "executions": "/api/executions"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/awx/create-template")
async def create_awx_job_template(
    request: AWXJobRequest, 
    db: Session = Depends(get_db),
    current_user: Optional[AnsibleBuilderUser] = Depends(get_optional_user_keycloak)
):
    """AWX에 새로운 Job Template 생성"""
    
    # 사용자 이름 추출 (SSO 또는 anonymous)
    username = current_user.username if current_user else "anonymous"
    
    # 🔴 DB 객체 조회
    playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == request.playbook_id
    ).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    inventory = db.query(AnsibleBuilderInventory).filter(
        AnsibleBuilderInventory.id == request.inventory_id
    ).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    # 🔴 DB 객체를 dict로 변환
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    
    inventory_dict = {
        "id": inventory.id,
        "name": inventory.name,
        "content": inventory.content
    }
    
    try:
        # AWX 인증 정보: 환경 변수 우선, request에서 제공된 값 사용 가능
        awx_url = request.awx_url or AWX_URL
        awx_token = request.awx_token or AWX_TOKEN

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {awx_token}"}

            # 0. 인증 테스트
            test_res = await client.get(f"{awx_url}/api/v2/me/", headers=headers)
            if test_res.status_code != 200:
                raise HTTPException(status_code=401, detail="AWX authentication failed")
            
            # 1. Organization 조회
            orgs_res = await client.get(f"{awx_url}/api/v2/organizations/", headers=headers)
            if orgs_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get organizations")
            
            orgs = orgs_res.json()
            if not orgs.get('results'):
                raise HTTPException(status_code=400, detail="No organizations found")
            org_id = orgs['results'][0]['id']
            
            # 2. Project 조회
            projects_url = f"{awx_url}/api/v2/projects/"
            projects_res = await client.get(projects_url, headers=headers)
            if projects_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get projects")
            
            projects = projects_res.json()
            if not projects.get('results'):
                raise HTTPException(status_code=400, detail="No projects found")
            
            # 환경 변수에서 기본 프로젝트 ID 사용, 없으면 Demo Project 찾기
            project_id = AWX_DEFAULT_PROJECT_ID
            if not project_id:
                for proj in projects['results']:
                    if 'demo' in proj['name'].lower():
                        project_id = proj['id']
                        break
            
            if not project_id:
                project_id = projects['results'][0]['id']
            
            # 3. Inventory 생성
            inventory_name = f"ansible_builder_{inventory_dict['id']}"
            inventories_url = f"{awx_url}/api/v2/inventories/"
            
            # 기존 Inventory 확인
            inv_check = await client.get(f"{inventories_url}?name={inventory_name}", headers=headers)
            if inv_check.status_code == 200 and inv_check.json().get('count', 0) > 0:
                awx_inventory_id = inv_check.json()['results'][0]['id']
            else:
                # 새 Inventory 생성
                inv_data = {
                    "name": inventory_name,
                    "description": "Auto-created by Ansible Builder",
                    "organization": org_id
                }
                inv_res = await client.post(inventories_url, headers=headers, json=inv_data)
                if inv_res.status_code not in [200, 201]:
                    raise HTTPException(status_code=400, detail=f"Failed to create inventory: {inv_res.text}")
                awx_inventory_id = inv_res.json()['id']
            
            # Host 추가 (간소화)
            hosts_url = f"{awx_url}/api/v2/inventories/{awx_inventory_id}/hosts/"
            for line in inventory_dict['content'].split('\n'):
                line = line.strip()
                if not line or line.startswith('[') or line.startswith('#'):
                    continue
                
                parts = line.split()
                if not parts:
                    continue
                
                hostname = parts[0]
                host_vars = {}
                for part in parts[1:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        host_vars[key] = value
                
                host_data = {
                    "name": hostname,
                    "description": "Auto-created",
                    "enabled": True
                }
                
                if host_vars:
                    host_data["variables"] = yaml.dump(host_vars)
                
                # 기존 호스트 확인
                check_url = f"{hosts_url}?name={hostname}"
                check_res = await client.get(check_url, headers=headers)
                
                if not (check_res.status_code == 200 and check_res.json().get('count', 0) > 0):
                    await client.post(hosts_url, headers=headers, json=host_data)
            
            # 4. Credential 조회
            creds_url = f"{awx_url}/api/v2/credentials/"
            creds_res = await client.get(creds_url, headers=headers)
            credential_id = None
            
            if creds_res.status_code == 200:
                creds = creds_res.json()
                for cred in creds.get('results', []):
                    if 'gaia_bot' in cred.get('name', '').lower():
                        credential_id = cred['id']
                        break
                
                if not credential_id and creds.get('results'):
                    credential_id = creds['results'][0]['id']
            
            # ⭐ 5. Job Template 생성 (templates_url 정의)
            templates_url = f"{awx_url}/api/v2/job_templates/"
            
            # 읽기 쉬운 템플릿 이름: [사용자] Playbook이름 @ 날짜시간
            short_date = datetime.now().strftime("%m%d_%H%M")
            template_name = f"[{username}] {playbook_dict['name']} @ {short_date}"
            
            # 기존 Template 확인
            template_check = await client.get(f"{templates_url}?name={template_name}", headers=headers)
            if template_check.status_code == 200 and template_check.json().get('count', 0) > 0:
                existing = template_check.json()['results'][0]
                return {
                    "status": "success",
                    "template_id": existing['id'],
                    "template_name": template_name,
                    "template_url": f"{awx_url}/#/templates/job_template/{existing['id']}",
                    "message": "Job Template already exists"
                }
            
            # Template 데이터 생성
            template_data = {
                "name": template_name,
                "description": f"Auto-created: {playbook_dict['name']}",
                "job_type": "run",
                "inventory": awx_inventory_id,
                "project": project_id,
                "playbook": "ansible_builder_executor.yml",
                "verbosity": 2,
                "ask_variables_on_launch": True,
                "ask_limit_on_launch": False,
                "ask_tags_on_launch": False,
                "ask_skip_tags_on_launch": False,
                "ask_job_type_on_launch": False,
                "ask_verbosity_on_launch": False,
                "ask_inventory_on_launch": False,
                "ask_credential_on_launch": False,
                # ⭐ extra_vars를 YAML 형식으로 전달 (AWX 호환성)
                "extra_vars": yaml.dump({
                    "builder_playbook_name": playbook_dict['name'],
                    "target_hosts": playbook_dict['hosts'],
                    "become_required": playbook_dict['become'],
                    "builder_tasks": playbook_dict['tasks']
                }, default_flow_style=False)
            }
            
            if credential_id:
                template_data["credentials"] = [credential_id]
            
            # Template 생성 요청
            template_res = await client.post(templates_url, headers=headers, json=template_data)
            if template_res.status_code not in [200, 201]:
                raise HTTPException(status_code=400, detail=f"Failed to create job template: {template_res.text}")
            
            template_result = template_res.json()
            
            return {
                "status": "success",
                "template_id": template_result['id'],
                "template_name": template_name,
                "template_url": f"{awx_url}/#/templates/job_template/{template_result['id']}",
                "project_id": project_id,
                "inventory_id": awx_inventory_id,
                "credential_id": credential_id,
                "message": f"Job Template '{template_name}' created successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    """AWX에 새로운 Job Template 생성"""
    # DEBUG: Write the executor content to a file for verification
    debug_file_path = "ansible_builder_executor_sent_to_awx.yml"
    with open(debug_file_path, "w") as f:
        f.write(EXECUTOR_PLAYBOOK_CONTENT)

    # 🔴 DB 객체 조회
    playbook = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == request.playbook_id).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    inventory = db.query(AnsibleBuilderInventory).filter(
        AnsibleBuilderInventory.id == request.inventory_id
    ).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    # 🔴 DB 객체를 dict로 변환 (중요!)
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    
    inventory_dict = {
        "id": inventory.id,
        "name": inventory.name,
        "content": inventory.content
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {request.awx_token or AWX_TOKEN}"}
            
            # 0. 인증 테스트
            try:
                test_res = await client.get(f"{awx_url}/api/v2/me/", headers=headers)
                if test_res.status_code != 200:
                    raise HTTPException(status_code=401, detail=f"AWX authentication failed: {test_res.text}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Cannot connect to AWX: {str(e)}")
            
            # 1. Organization 조회
            orgs_res = await client.get(f"{awx_url}/api/v2/organizations/", headers=headers)
            if orgs_res.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to get organizations: {orgs_res.text}")
            orgs = orgs_res.json()
            if not orgs.get('results'):
                raise HTTPException(status_code=400, detail="No organizations found in AWX")
            org_id = orgs['results'][0]['id']
            
            # 2. 기존 Project 중 하나 사용 (Demo Project 우선)
            projects_url = f"{awx_url}/api/v2/projects/"
            projects_res = await client.get(projects_url, headers=headers)
            if projects_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get projects")
            
            projects = projects_res.json()
            if not projects.get('results'):
                raise HTTPException(status_code=400, detail="No projects found in AWX. Please create at least one project with playbooks first.")
            
            # 환경 변수에서 기본 프로젝트 ID 사용, 없으면 Demo Project 찾기
            project_id = AWX_DEFAULT_PROJECT_ID
            demo_playbook = None
            
            if project_id:
                # 환경 변수로 지정된 프로젝트 사용
                playbooks_url = f"{awx_url}/api/v2/projects/{project_id}/playbooks/"
                pb_res = await client.get(playbooks_url, headers=headers)
                if pb_res.status_code == 200:
                    pbs = pb_res.json()
                    if pbs:
                        demo_playbook = pbs[0]
            else:
                # Demo Project 찾기 또는 첫 번째 Project 사용
                for proj in projects['results']:
                    if 'demo' in proj['name'].lower() or 'example' in proj['name'].lower():
                        project_id = proj['id']
                        playbooks_url = f"{awx_url}/api/v2/projects/{project_id}/playbooks/"
                        pb_res = await client.get(playbooks_url, headers=headers)
                        if pb_res.status_code == 200:
                            pbs = pb_res.json()
                            if pbs:
                                demo_playbook = pbs[0]
                        break
            
            if not project_id:
                project_id = projects['results'][0]['id']
                playbooks_url = f"{awx_url}/api/v2/projects/{project_id}/playbooks/"
                pb_res = await client.get(playbooks_url, headers=headers)
                if pb_res.status_code == 200:
                    pbs = pb_res.json()
                    if pbs:
                        demo_playbook = pbs[0]
            
            if not demo_playbook:
                raise HTTPException(status_code=400, detail="No playbooks found in AWX projects. Please sync a project first.")
            
            # 3. Inventory 생성
            inventory_name = f"ansible_builder_{inventory_dict['id']}"
            inventories_url = f"{awx_url}/api/v2/inventories/"
            
            # 기존 Inventory 확인
            inv_check = await client.get(f"{inventories_url}?name={inventory_name}", headers=headers)
            if inv_check.status_code == 200 and inv_check.json().get('count', 0) > 0:
                awx_inventory_id = inv_check.json()['results'][0]['id']
                # 기존 Inventory의 Host 삭제 후 재생성
                hosts_list_url = f"{awx_url}/api/v2/inventories/{awx_inventory_id}/hosts/"
                existing_hosts = await client.get(hosts_list_url, headers=headers)
                if existing_hosts.status_code == 200:
                    for host in existing_hosts.json().get('results', []):
                        await client.delete(f"{awx_url}/api/v2/hosts/{host['id']}/", headers=headers)
            else:
                # 새 Inventory 생성
                inv_data = {
                    "name": inventory_name,
                    "description": f"Auto-created by Ansible Builder",
                    "organization": org_id
                }
                inv_res = await client.post(inventories_url, headers=headers, json=inv_data)
                if inv_res.status_code not in [200, 201]:
                    raise HTTPException(status_code=400, detail=f"Failed to create inventory: {inv_res.text}")
                awx_inventory_id = inv_res.json()['id']
            
            # Host 추가 - 철저한 변수 필터링 및 그룹 할당
            hosts_url = f"{awx_url}/api/v2/inventories/{awx_inventory_id}/hosts/"
            groups_url = f"{awx_url}/api/v2/inventories/{awx_inventory_id}/groups/"
            
            current_group = None
            current_group_id = None
            added_hosts = set()
            skip_section = False
            created_groups = {}  # 그룹명 -> 그룹ID 매핑
            
            # 예약된 그룹명 (AWX에서 생성 불가)
            RESERVED_GROUPS = ['all', 'ungrouped', 'localhost']
            
            for line in inventory_dict['content'].split('\n'):
                line = line.strip()
                
                if not line:
                    continue
                
                # 주석 처리
                if line.startswith('#') or line.startswith(';'):
                    continue
                
                # 그룹 헤더
                if line.startswith('[') and line.endswith(']'):
                    current_group = line[1:-1]
                    
                    if ':vars' in current_group or ':children' in current_group:
                        skip_section = True
                        current_group_id = None
                        print(f"🚫 Skip section: [{current_group}]")
                    else:
                        skip_section = False
                        print(f"✅ Process section: [{current_group}]")
                        
                        # 예약된 그룹은 생성하지 않음 (호스트는 직접 인벤토리에 추가)
                        if current_group.lower() in RESERVED_GROUPS:
                            print(f"⚠️ Reserved group '{current_group}', skipping group creation")
                            current_group_id = None
                        # AWX에 그룹 생성
                        elif current_group not in created_groups:
                            try:
                                # 기존 그룹 확인
                                check_group = await client.get(f"{groups_url}?name={current_group}", headers=headers)
                                if check_group.status_code == 200 and check_group.json().get('count', 0) > 0:
                                    current_group_id = check_group.json()['results'][0]['id']
                                    created_groups[current_group] = current_group_id
                                    print(f"✅ Group exists: {current_group} (ID: {current_group_id})")
                                else:
                                    # 새 그룹 생성
                                    group_data = {
                                        "name": current_group,
                                        "description": f"Auto-created from inventory",
                                        "inventory": awx_inventory_id
                                    }
                                    group_res = await client.post(groups_url, headers=headers, json=group_data)
                                    if group_res.status_code in [200, 201]:
                                        current_group_id = group_res.json()['id']
                                        created_groups[current_group] = current_group_id
                                        print(f"✅ Created group: {current_group} (ID: {current_group_id})")
                                    else:
                                        print(f"⚠️ Failed to create group {current_group}: {group_res.text}")
                                        current_group_id = None
                            except Exception as e:
                                print(f"⚠️ Error creating group {current_group}: {str(e)}")
                                current_group_id = None
                        else:
                            current_group_id = created_groups[current_group]
                    
                    continue
                
                # :vars/:children 섹션 내부 스킵
                if skip_section:
                    print(f"🚫 Skip (special): {line[:60]}")
                    continue
                
                if not current_group:
                    continue
                
                parts = line.split()
                if not parts:
                    continue
                
                hostname = parts[0]
                
                # 빈 호스트명, 특수문자 차단
                if not hostname or len(hostname) < 2 or hostname in [';', '#', ',', '|', '']:
                    continue
                
                # = 있고 ansible_ 아니면 변수
                if '=' in hostname and not hostname.startswith('ansible_'):
                    print(f"🚫 Variable: {line[:60]}")
                    continue
                
                # 언더스코어 변수 패턴
                if '_' in hostname and not any(c in hostname for c in ['.', '-', '@', ':']):
                    print(f"🚫 Underscore var: {line[:60]}")
                    continue
                
                # 변수 키워드 차단
                keywords = ['version', 'endpoint', 'iface', 'tunnel', 'plugins', 'kubernetes', 'containerd', 'runc', 'etcd', 'kube', 'cni']
                check_name = hostname.split('=')[0].lower() if '=' in hostname else hostname.lower()
                
                if check_name != 'localhost' and any(kw in check_name for kw in keywords):
                    print(f"🚫 Keyword: {line[:60]}")
                    continue
                
                # 중복 체크
                if hostname in added_hosts:
                    continue
                
                # 호스트 변수 파싱
                host_vars = {}
                for part in parts[1:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        host_vars[key] = value
                
                host_data = {
                    "name": hostname,
                    "description": f"Auto-created from inventory",
                    "enabled": True
                }
                
                if host_vars:
                    host_data["variables"] = yaml.dump(host_vars)
                
                try:
                    # 기존 호스트 체크
                    check_url = f"{hosts_url}?name={hostname}"
                    check_res = await client.get(check_url, headers=headers)
                    
                    host_id = None
                    if check_res.status_code == 200 and check_res.json().get('count', 0) > 0:
                        host_id = check_res.json()['results'][0]['id']
                        print(f"Host exists: {hostname} (ID: {host_id})")
                        added_hosts.add(hostname)
                    else:
                        # 새 호스트 추가
                        host_res = await client.post(hosts_url, headers=headers, json=host_data)
                        if host_res.status_code in [200, 201]:
                            host_id = host_res.json()['id']
                            added_hosts.add(hostname)
                            print(f"✅ Added host: {hostname} (ID: {host_id})")
                        else:
                            print(f"⚠️ Failed to add {hostname}: {host_res.text}")
                    
                    # 호스트를 그룹에 추가
                    if host_id and current_group_id:
                        associate_url = f"{awx_url}/api/v2/groups/{current_group_id}/hosts/"
                        associate_data = {"id": host_id}
                        associate_res = await client.post(associate_url, headers=headers, json=associate_data)
                        if associate_res.status_code in [200, 201, 204]:
                            print(f"✅ Added {hostname} to group {current_group}")
                        else:
                            # 이미 그룹에 속해있을 수 있음 (무시)
                            print(f"ℹ️ Host {hostname} association: {associate_res.status_code}")
                    
                except Exception as e:
                    print(f"⚠️ Error processing {hostname}: {str(e)}")
            
            # 4. Credential 조회
            # gaia_bot 이름을 포함하는 credential 검색 (API 필터링 사용)
            creds_url = f"{awx_url}/api/v2/credentials/?name__icontains=gaia_bot"
            creds_res = await client.get(creds_url, headers=headers)
            credential_id = None
            
            if creds_res.status_code == 200:
                creds = creds_res.json()
                if creds.get('results'):
                    # 첫 번째 매칭되는 결과 사용
                    cred = creds['results'][0]
                    credential_id = cred['id']
                    print(f"Found gaia_bot credential: {cred['name']} (ID: {credential_id})")
                
                if not credential_id:
                    machine_creds_url = f"{awx_url}/api/v2/credentials/?credential_type=1"
                    machine_creds_res = await client.get(machine_creds_url, headers=headers)
                    if machine_creds_res.status_code == 200:
                        machine_creds = machine_creds_res.json()
                        if machine_creds.get('results'):
                            credential_id = machine_creds['results'][0]['id']
                            print(f"Using fallback credential: {machine_creds['results'][0]['name']} (ID: {credential_id})")
            
            # Job Template 생성
                template_res = await client.post(templates_url, headers=headers, json=template_data)
                if template_res.status_code not in [200, 201]:
                    raise HTTPException(status_code=400, detail=f"Failed to create job template: {template_res.text}")

                template_result = template_res.json()
                template_id = template_result['id']

                # ⭐ Survey 생성
                survey_spec = {
                    "name": "Ansible Builder Variables",
                    "description": "Dynamic playbook execution variables",
                    "spec": [
            {
                "question_name": "Builder Tasks JSON",
                "question_description": "JSON array of tasks to execute",
                "required": True,
                "type": "textarea",
                "variable": "builder_tasks",
                "min": 0,
                "max": 65536,
                "default": json.dumps(playbook_dict['tasks'])
            },
            {
                "question_name": "Target Hosts",
                "question_description": "Hosts pattern",
                "required": True,
                "type": "text",
                "variable": "target_hosts",
                "min": 0,
                "max": 1024,
                "default": playbook_dict['hosts']
            },
            {
                "question_name": "Become (sudo)",
                "question_description": "Run with elevated privileges",
                "required": True,
                "type": "multiplechoice",
                "variable": "become_required",
                "choices": ["true", "false"],
                "default": str(playbook_dict['become']).lower()
            }
        ]
    }
    
            survey_url = f"{awx_url}/api/v2/job_templates/{template_id}/survey_spec/"
            survey_res = await client.post(survey_url, headers=headers, json=survey_spec)

            if survey_res.status_code not in [200, 201]:
                print(f"⚠️ Survey creation failed: {survey_res.text}")

            return {
                "status": "success",
                "template_id": template_id,
                "template_name": template_name,
                "template_url": f"{awx_url}/#/templates/job_template/{template_id}",
                "message": "Job Template created with survey"
            }



            # 5. Job Template 생성
            # 읽기 쉬운 템플릿 이름: [사용자] Playbook이름 @ 날짜시간
            short_date = datetime.now().strftime("%m%d_%H%M")
            template_name = f"[{username}] {playbook_dict['name']} @ {short_date}"
            templates_url = f"{awx_url}/api/v2/job_templates/"
            
            # 기존 Template 확인
            template_check = await client.get(f"{templates_url}?name={template_name}", headers=headers)
            if template_check.status_code == 200 and template_check.json().get('count', 0) > 0:
                existing = template_check.json()['results'][0]
                return {
                    "status": "success",
                    "template_id": existing['id'],
                    "template_name": template_name,
                    "template_url": f"{awx_url}/#/templates/job_template/{existing['id']}",
                    "message": f"Job Template '{template_name}' already exists"
                }
            
            # Playbook YAML을 Project에 업로드하는 대신, 
            # AWX의 기존 playbook을 사용하고 extra_vars로 동작 제어
            # Demo Project에서 ansible_builder_executor.yml 사용
            demo_playbook_file = "ansible_builder_executor.yml"
            
            template_data = {
                "name": template_name,
                "description": f"Auto-created: {playbook_dict['name']} on {inventory_dict['name']}\n\nDynamic execution via extra_vars",
                "job_type": "run",
                "inventory": awx_inventory_id,
                "project": project_id,
                "playbook": demo_playbook_file,
                "verbosity": 1,
                "ask_variables_on_launch": True,
                "extra_vars": yaml.dump({
                    "builder_playbook_name": playbook_dict['name'],
                    "target_hosts": playbook_dict['hosts'],
                    "become_required": playbook_dict['become'],
                    "builder_tasks": playbook_dict['tasks']
                }, default_flow_style=False)
            }
            
            if credential_id:
                template_data["credentials"] = [credential_id]
            
            template_res = await client.post(templates_url, headers=headers, json=template_data)
            if template_res.status_code not in [200, 201]:
                raise HTTPException(status_code=400, detail=f"Failed to create job template: {template_res.text}")
            
            template_result = template_res.json()
            
            return {
                "status": "success",
                "template_id": template_result['id'],
                "template_name": template_name,
                "template_url": f"{awx_url}/#/templates/job_template/{template_result['id']}",
                "project_id": project_id,
                "inventory_id": awx_inventory_id,
                "inventory_url": f"{awx_url}/#/inventories/inventory/{awx_inventory_id}/hosts",
                "credential_id": credential_id,
                "message": f"Job Template '{template_name}' created successfully"
            }
            
    except HTTPException:
        raise
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        error_detail = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)


@app.post("/api/awx/launch")
async def launch_awx_job(request: AWXJobRequest, db: Session = Depends(get_db)):
    """AWX Job 실행 - extra_vars 직접 전달"""

    playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == request.playbook_id
    ).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }

    try:
        # AWX 인증 정보: 환경 변수 우선, request에서 제공된 값 사용 가능
        awx_url = request.awx_url or AWX_URL
        awx_token = request.awx_token or AWX_TOKEN

        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {awx_token}"}
            
            if not request.job_template_id:
                raise HTTPException(status_code=400, detail="Job Template ID required")
            
            # ⭐ Launch URL
            launch_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/launch/"
            
            # ⭐ extra_vars 준비
            extra_vars = {
                "builder_playbook_name": playbook_dict['name'],
                "target_hosts": playbook_dict['hosts'],
                "become_required": playbook_dict['become'],
                "builder_tasks": playbook_dict['tasks']
            }
            
            # ⭐ AWX API 형식: extra_vars는 YAML 문자열로 전달
            launch_payload = {
                "extra_vars": yaml.dump(extra_vars, default_flow_style=False)
            }
            
            print(f"🚀 Launching job with payload:")
            print(json.dumps(launch_payload, indent=2))
            
            response = await client.post(launch_url, headers=headers, json=launch_payload)
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Launch failed: {response.text}"
                )
            
            job_result = response.json()
            job_id = job_result.get("id")
            
            return {
                "status": "success",
                "awx_job_id": job_id,
                "awx_job_url": f"{awx_url}/#/jobs/playbook/{job_id}/output",
                "playbook_name": playbook_dict['name'],
                "tasks_count": len(playbook_dict['tasks']),
                "message": f"Executing {len(playbook_dict['tasks'])} tasks"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    """AWX Job 실행 - Template 업데이트 후 Launch"""
    
    playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == request.playbook_id
    ).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {request.awx_token or AWX_TOKEN}"}
            
            if not request.job_template_id:
                raise HTTPException(status_code=400, detail="Job Template ID required")
            
            template_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/"
            
            # STEP 1: Template extra_vars 업데이트
            extra_vars_data = {
                "builder_playbook_name": playbook_dict['name'],
                "target_hosts": playbook_dict['hosts'],
                "become_required": playbook_dict['become'],
                "builder_tasks": playbook_dict['tasks']
            }
            
            update_payload = {
                "extra_vars": yaml.dump(extra_vars_data, default_flow_style=False)
            }
            
            update_res = await client.patch(template_url, headers=headers, json=update_payload)
            
            if update_res.status_code not in [200, 201]:
                print(f"⚠️ Template update warning: {update_res.text}")
            
            # STEP 2: Launch Job
            launch_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/launch/"
            
            response = await client.post(launch_url, headers=headers, json={})
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Launch failed: {response.text}"
                )
            
            job_result = response.json()
            job_id = job_result.get("id")
            
            return {
                "status": "success",
                "awx_job_id": job_id,
                "awx_job_url": f"{awx_url}/#/jobs/playbook/{job_id}/output",
                "tasks_count": len(playbook_dict['tasks']),
                "message": f"Executing {len(playbook_dict['tasks'])} tasks"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    """AWX Job 실행 - Template 수정 후 Launch"""
    
    playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == request.playbook_id
    ).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {request.awx_token or AWX_TOKEN}"}
            
            if not request.job_template_id:
                raise HTTPException(status_code=400, detail="Job Template ID required")
            
            template_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/"
            
            # ⭐ STEP 1: Template의 extra_vars 업데이트
            extra_vars_data = {
                "builder_playbook_name": playbook_dict['name'],
                "target_hosts": playbook_dict['hosts'],
                "become_required": playbook_dict['become'],
                "builder_tasks": playbook_dict['tasks']
            }
            
            update_payload = {
                "extra_vars": yaml.dump(extra_vars_data, default_flow_style=False)
            }
            
            print(f"📝 Updating template with extra_vars:\n{json.dumps(extra_vars_data, indent=2)}")
            
            update_res = await client.patch(template_url, headers=headers, json=update_payload)
            
            if update_res.status_code not in [200, 201]:
                print(f"⚠️ Template update failed: {update_res.text}")
            else:
                print(f"✅ Template updated successfully")
            
            # ⭐ STEP 2: Launch Job (extra_vars는 이미 Template에 저장됨)
            launch_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/launch/"
            
            # 빈 payload로 launch (Template의 extra_vars 사용)
            launch_payload = {}
            
            response = await client.post(launch_url, headers=headers, json=launch_payload)
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Launch failed: {response.text}"
                )
            
            job_result = response.json()
            job_id = job_result.get("id")
            
            # Job 상세 확인
            await asyncio.sleep(1)
            job_detail_url = f"{awx_url}/api/v2/jobs/{job_id}/"
            job_detail_res = await client.get(job_detail_url, headers=headers)
            
            actual_vars = "unknown"
            if job_detail_res.status_code == 200:
                job_detail = job_detail_res.json()
                actual_vars = job_detail.get("extra_vars", "{}")
                print(f"✅ Job {job_id} extra_vars:\n{actual_vars}")
            
            return {
                "status": "success",
                "awx_job_id": job_id,
                "awx_job_url": f"{awx_url}/#/jobs/playbook/{job_id}/output",
                "extra_vars_set": json.dumps(extra_vars_data, indent=2),
                "extra_vars_actual": actual_vars,
                "message": "Job launched successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    """AWX Job 실행 - extra_vars 강제 주입"""
    
    playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == request.playbook_id
    ).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {request.awx_token or AWX_TOKEN}"}
            
            if not request.job_template_id:
                raise HTTPException(status_code=400, detail="Job Template ID required")
            
            # ⭐ Launch 전에 Template의 extra_vars 확인
            template_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/"
            template_res = await client.get(template_url, headers=headers)
            
            if template_res.status_code != 200:
                raise HTTPException(status_code=404, detail="Template not found")
            
            template = template_res.json()
            
            # ⭐ 기존 extra_vars와 병합
            existing_vars = json.loads(template.get('extra_vars', '{}'))
            
            # ⭐ 새로운 extra_vars 생성
            new_extra_vars = {
                **existing_vars,  # 기존 변수 유지
                "builder_playbook_name": playbook_dict['name'],
                "target_hosts": playbook_dict['hosts'],
                "become_required": playbook_dict['become'],
                "builder_tasks": playbook_dict['tasks']
            }
            
            launch_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/launch/"
            
            # ⭐ AWX API 형식: extra_vars는 YAML 문자열
            job_data = {
                "extra_vars": yaml.dump(new_extra_vars, default_flow_style=False)
            }
            
            print(f"🚀 Launching with extra_vars:\n{json.dumps(new_extra_vars, indent=2)}")
            
            response = await client.post(launch_url, headers=headers, json=job_data)
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Launch failed: {response.text}"
                )
            
            job_result = response.json()
            job_id = job_result.get("id")
            
            # ⭐ Job 상세 조회로 실제 적용된 extra_vars 확인
            await asyncio.sleep(1)  # Job이 생성될 시간 대기
            job_detail_url = f"{awx_url}/api/v2/jobs/{job_id}/"
            job_detail_res = await client.get(job_detail_url, headers=headers)
            
            actual_vars = "unknown"
            if job_detail_res.status_code == 200:
                job_detail = job_detail_res.json()
                actual_vars = job_detail.get("extra_vars", "{}")
                print(f"✅ Job created with extra_vars:\n{actual_vars}")
            
            return {
                "status": "success",
                "awx_job_id": job_id,
                "awx_job_url": f"{awx_url}/#/jobs/playbook/{job_id}/output",
                "extra_vars_sent": json.dumps(new_extra_vars, indent=2),
                "extra_vars_actual": actual_vars,
                "message": "Job launched successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    """AWX Job 실행 - extra_vars 강제 주입"""
    
    playbook = db.query(AnsibleBuilderPlaybook).filter(
        AnsibleBuilderPlaybook.id == request.playbook_id
    ).first()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    playbook_dict = {
        "name": playbook.name,
        "hosts": playbook.hosts,
        "become": playbook.become,
        "tasks": json.loads(playbook.tasks)
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {request.awx_token or AWX_TOKEN}"}
            
            if not request.job_template_id:
                raise HTTPException(status_code=400, detail="Job Template ID required")
            
            # ⭐ extra_vars를 문자열로 전달 (AWX 요구사항)
            extra_vars_str = json.dumps({
                "builder_playbook_name": playbook_dict['name'],
                "target_hosts": playbook_dict['hosts'],
                "become_required": playbook_dict['become'],
                "builder_tasks": playbook_dict['tasks']
            })
            
            launch_url = f"{awx_url}/api/v2/job_templates/{request.job_template_id}/launch/"
            
            # ⭐ AWX API 형식: extra_vars는 문자열
            job_data = {
                "extra_vars": extra_vars_str
            }
            
            print(f"🚀 Launching job with data: {json.dumps(job_data, indent=2)}")
            
            response = await client.post(launch_url, headers=headers, json=job_data)
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Launch failed: {response.text}"
                )
            
            job_result = response.json()
            job_id = job_result.get("id")
            
            # ⭐ Job 상세 조회로 extra_vars 확인
            job_detail_url = f"{awx_url}/api/v2/jobs/{job_id}/"
            job_detail = await client.get(job_detail_url, headers=headers)
            
            actual_extra_vars = job_detail.json().get("extra_vars", "{}") if job_detail.status_code == 200 else "unknown"
            
            return {
                "status": "success",
                "awx_job_id": job_id,
                "awx_job_url": f"{awx_url}/#/jobs/playbook/{job_id}/output",
                "extra_vars_sent": extra_vars_str,
                "extra_vars_received": actual_extra_vars,
                "message": "Job launched"
            }
            
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/awx/templates")
async def get_awx_templates(
    awx_url: Optional[str] = None,
    awx_token: Optional[str] = None
):
    """AWX Job Templates 목록 조회"""
    # 환경 변수에서 AWX 인증 정보 가져오기
    awx_url = awx_url or AWX_URL
    awx_token = awx_token or AWX_TOKEN

    try:
        async with httpx.AsyncClient(verify=False) as client:
            headers = {"Authorization": f"Bearer {awx_token}"}
            url = f"{awx_url}/api/v2/job_templates/"
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch templates from AWX")
            
            data = response.json()
            templates = [
                {"id": t["id"], "name": t["name"], "description": t.get("description", "")}
                for t in data.get("results", [])
            ]
            
            return {"templates": templates}
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to AWX: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AWX integration error: {str(e)}")


@app.get("/api/awx/inventories")
async def get_awx_inventories(
    awx_url: Optional[str] = None,
    awx_token: Optional[str] = None
):
    """AWX Inventories 목록 조회 (외부 API)"""
    awx_url = awx_url or AWX_URL
    awx_token = awx_token or AWX_TOKEN

    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {awx_token}"}
            url = f"{awx_url}/api/v2/inventories/"
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch inventories from AWX")
            
            data = response.json()
            inventories = [
                {
                    "id": inv["id"], 
                    "name": inv["name"], 
                    "description": inv.get("description", ""),
                    "total_hosts": inv.get("total_hosts", 0)
                }
                for inv in data.get("results", [])
            ]
            
            return {"inventories": inventories}
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to AWX: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AWX integration error: {str(e)}")

# inventory rebalance

@app.post("/api/inventories/import")
async def import_inventory_from_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """INI 파일을 업로드하여 Inventory 자동 생성"""
    try:
        content = await file.read()
        inventory_content = content.decode('utf-8')
        
        # 파일명에서 인벤토리 이름 추출
        inventory_name = file.filename.replace('.ini', '').replace('.txt', '')
        inventory_name = f"Imported_{inventory_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # 인벤토리 내용 검증
        if not inventory_content.strip():
            raise HTTPException(status_code=400, detail="Empty inventory file")
        
        # DB에 저장
        db_inventory = AnsibleBuilderInventory(
            name=inventory_name,
            content=inventory_content
        )
        db.add(db_inventory)
        db.commit()
        db.refresh(db_inventory)
        
        # 호스트 개수 카운트
        host_count = len([line for line in inventory_content.split('\n') 
                         if line.strip() and not line.strip().startswith('[') 
                         and not line.strip().startswith('#')])
        
        return {
            "status": "success",
            "inventory_id": db_inventory.id,
            "inventory_name": inventory_name,
            "host_count": host_count,
            "message": f"Successfully imported inventory with {host_count} hosts"
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.post("/api/inventories/import-text")
async def import_inventory_from_text(data: dict, db: Session = Depends(get_db)):
    """텍스트로 Inventory 대량 생성"""
    try:
        inventory_text = data.get('content', '')
        inventory_name = data.get('name', f'Imported_Inventory_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
        
        if not inventory_text.strip():
            raise HTTPException(status_code=400, detail="Empty inventory content")
        
        # DB에 저장
        db_inventory = AnsibleBuilderInventory(
            name=inventory_name,
            content=inventory_text
        )
        db.add(db_inventory)
        db.commit()
        db.refresh(db_inventory)
        
        # 호스트 개수 카운트
        host_count = len([line for line in inventory_text.split('\n') 
                         if line.strip() and not line.strip().startswith('[') 
                         and not line.strip().startswith('#')])
        
        return {
            "status": "success",
            "inventory_id": db_inventory.id,
            "inventory_name": inventory_name,
            "host_count": host_count,
            "message": f"Successfully imported inventory with {host_count} hosts"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.post("/api/inventories/import-csv")
async def import_inventory_from_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """CSV 파일에서 Inventory 생성 (hostname,user,port,connection)"""
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        lines = csv_content.strip().split('\n')
        if len(lines) < 2:
            raise HTTPException(status_code=400, detail="CSV must have header and at least one host")
        
        # 헤더 파싱
        header = [h.strip().lower() for h in lines[0].split(',')]
        
        # 필수 컬럼 확인
        if 'hostname' not in header and 'host' not in header:
            raise HTTPException(status_code=400, detail="CSV must have 'hostname' or 'host' column")
        
        hostname_idx = header.index('hostname') if 'hostname' in header else header.index('host')
        user_idx = header.index('user') if 'user' in header else header.index('ansible_user') if 'ansible_user' in header else None
        port_idx = header.index('port') if 'port' in header else header.index('ansible_port') if 'ansible_port' in header else None
        conn_idx = header.index('connection') if 'connection' in header else header.index('ansible_connection') if 'ansible_connection' in header else None
        group_idx = header.index('group') if 'group' in header else None
        
        # 그룹별로 호스트 정리
        groups = {}
        for i, line in enumerate(lines[1:], start=2):
            if not line.strip():
                continue
            
            try:
                parts = [p.strip() for p in line.split(',')]
                hostname = parts[hostname_idx]
                
                if not hostname:
                    continue
                
                group = parts[group_idx] if group_idx is not None and group_idx < len(parts) else 'default'
                
                if group not in groups:
                    groups[group] = []
                
                host_line = hostname
                if user_idx is not None and user_idx < len(parts) and parts[user_idx]:
                    host_line += f" ansible_user={parts[user_idx]}"
                if port_idx is not None and port_idx < len(parts) and parts[port_idx]:
                    host_line += f" ansible_port={parts[port_idx]}"
                if conn_idx is not None and conn_idx < len(parts) and parts[conn_idx]:
                    host_line += f" ansible_connection={parts[conn_idx]}"
                
                groups[group].append(host_line)
                
            except IndexError as e:
                print(f"Warning: Skipping malformed line {i}: {line}")
                continue
        
        # INI 형식으로 변환
        inventory_content = ""
        total_hosts = 0
        for group, hosts in groups.items():
            inventory_content += f"[{group}]\n"
            for host in hosts:
                inventory_content += f"{host}\n"
                total_hosts += 1
            inventory_content += "\n"
        
        # 파일명에서 인벤토리 이름 추출
        inventory_name = file.filename.replace('.csv', '')
        inventory_name = f"Imported_{inventory_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # DB에 저장
        db_inventory = AnsibleBuilderInventory(
            name=inventory_name,
            content=inventory_content.strip()
        )
        db.add(db_inventory)
        db.commit()
        db.refresh(db_inventory)
        
        return {
            "status": "success",
            "inventory_id": db_inventory.id,
            "inventory_name": inventory_name,
            "host_count": total_hosts,
            "group_count": len(groups),
            "message": f"Successfully imported {total_hosts} hosts in {len(groups)} groups"
        }
        
    except HTTPException:
        # Re-raise HTTPException as is (from validation)
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8")
    except Exception as e:
        error_detail = f"Import failed: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


# AWX Executor Playbook 자동 설정

EXECUTOR_PLAYBOOK_CONTENT = """---
- name: Ansible Builder Executor - DEEP DEBUG v2
  hosts: localhost
  connection: local
  gather_facts: no
  become: no

  tasks:
    - name: CONFIRMATION - This is the DEEP DEBUG v2 playbook
      ansible.builtin.debug:
        msg: "You are running the correct debugging playbook. Please provide the full output."

    - name: Display all available variables
      ansible.builtin.debug:
        var: hostvars[inventory_hostname]
"""

async def ensure_executor_playbook_exists(awx_url: str, awx_token: str, project_id: int) -> tuple:
    """AWX Project에 executor playbook이 있는지 확인하고 없으면 생성 안내"""
    
    executor_filename = "ansible_builder_executor.yml"

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {awx_token}"}

        # Project의 playbook 목록 조회
        playbooks_url = f"{awx_url}/api/v2/projects/{project_id}/playbooks/"
        
        try:
            pb_res = await client.get(playbooks_url, headers=headers)
            if pb_res.status_code == 200:
                playbooks = pb_res.json()
                
                # executor playbook이 이미 존재하는지 확인
                if executor_filename in playbooks:
                    print(f"✅ Executor playbook exists: {executor_filename}")
                    return (True, executor_filename, None)
                else:
                    print(f"⚠️ Executor playbook NOT found: {executor_filename}")
                    print(f"Available playbooks: {playbooks}")
                    
                    # Project 정보 조회
                    proj_res = await client.get(f"{awx_url}/api/v2/projects/{project_id}/", headers=headers)
                    if proj_res.status_code == 200:
                        project_info = proj_res.json()
                        project_name = project_info.get('name', 'Unknown')
                        scm_type = project_info.get('scm_type', '')
                        scm_url = project_info.get('scm_url', '')
                        local_path = project_info.get('local_path', '')
                        
                        print(f"Project: {project_name}, SCM: {scm_type}, Local: {local_path}")
                        
                        # SCM 기반 프로젝트인 경우
                        if scm_type in ['git', 'svn', 'hg']:
                            instructions = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚙️  EXECUTOR SETUP REQUIRED\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nProject: {project_name}\nType: {scm_type.upper()}\nRepository: {scm_url}\n\nSTEP 1: Add file to your repository\n────────────────────────────────────────\nFile: {executor_filename}\nLocation: Root of repository\n\nSTEP 2: Commit and push\n────────────────────────────────────────\ngit add {executor_filename}\ngit commit -m \"Add Ansible Builder executor\"\ngit push\n\nSTEP 3: Sync project in AWX\n────────────────────────────────────────\nAWX → Projects → {project_name} → Sync\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                            return (False, None, instructions)
                        
                        # Manual 프로젝트인 경우
                        else:
                            if local_path:
                                project_path = f"/var/lib/awx/projects/{local_path}"
                            else: 
                                # local_path가 없으면 project name 사용
                                project_path = f"/var/lib/awx/projects/{project_name}"
                            
                            instructions = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚙️  EXECUTOR SETUP REQUIRED (Manual Project)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nProject: {project_name}\nType: Manual\nPath: {project_path}\n\nRUN THIS ON AWX SERVER:\n────────────────────────────────────────\nsudo mkdir -p {project_path}\nsudo chown awx:awx {project_path}\n\ncat > {project_path}/{executor_filename} << 'EOF'\n{EXECUTOR_PLAYBOOK_CONTENT}EOF\n\nsudo chown awx:awx {project_path}/{executor_filename}\n\nTHEN VERIFY:\n────────────────────────────────────────\nls -la {project_path}/{executor_filename}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nALTERNATIVE (if no SSH access):\nUse existing playbook temporarily until setup is complete.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                            return (False, None, instructions)
                    
                    # 기본 안내
                    return (False, None, "Executor playbook not found. Please add ansible_builder_executor.yml to your AWX project.")
            else:
                # API 호출 실패 시 상세 에러 반환
                error_detail = f"Failed to get playbooks from AWX (status: {pb_res.status_code}, project_id: {project_id})"
                print(f"⚠️ {error_detail}")
                return (False, None, f"{error_detail}. Check AWX connection and credentials.")
        
        except Exception as e:
            error_msg = f"Error checking executor playbook: {str(e)}"
            print(error_msg)
            return (False, None, error_msg)
    
    return (False, None, f"Unable to verify executor playbook for project_id={project_id}. AWX URL: {awx_url}")


@app.get("/api/awx/config")
async def get_awx_config():
    """기본 AWX 설정 반환"""
    return {
        "url": AWX_URL,
        "default_project_id": AWX_DEFAULT_PROJECT_ID,
        "default_job_template_id": AWX_DEFAULT_JOB_TEMPLATE_ID
    }

@app.get("/api/awx/check-executor")
async def check_awx_executor(
    project_id: Optional[int] = None,
    awx_url: Optional[str] = None,
    awx_token: Optional[str] = None
):
    """Executor playbook 존재 여부 확인"""
    # 환경 변수에서 AWX 인증 정보 가져오기
    awx_url = awx_url or AWX_URL
    awx_token = awx_token or AWX_TOKEN
    
    try:
        # project_id가 없으면 환경 변수 또는 자동으로 찾기
        if not project_id:
            # 1. 환경 변수에서 기본 프로젝트 ID 사용
            if AWX_DEFAULT_PROJECT_ID:
                project_id = AWX_DEFAULT_PROJECT_ID
                print(f"✓ Using default project ID from environment: {project_id}")
            else:
                # 2. 자동으로 찾기 (Demo Project 우선)
                async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                    headers = {"Authorization": f"Bearer {awx_token}"}
                    projects_res = await client.get(f"{awx_url}/api/v2/projects/", headers=headers)
                    
                    if projects_res.status_code == 200:
                        projects = projects_res.json().get('results', [])
                        
                        # 'demo'가 포함된 프로젝트 찾기
                        for proj in projects:
                            if 'demo' in proj['name'].lower():
                                project_id = proj['id']
                                break
                        
                        # 없으면 첫 번째 프로젝트 사용
                        if not project_id and projects:
                            project_id = projects[0]['id']
                
                if not project_id:
                     return {
                        "status": "setup_required",
                        "executor_playbook": None,
                        "instructions": "No AWX Project found. Please create a Project in AWX first.",
                        "playbook_content": EXECUTOR_PLAYBOOK_CONTENT
                    }

        exists, filename, instructions = await ensure_executor_playbook_exists(
            awx_url, awx_token, project_id
        )
        
        if exists:
            return {
                "status": "ready",
                "executor_playbook": filename,
                "project_id": project_id,
                "message": "Executor playbook is available"
            }
        else:
            return {
                "status": "setup_required",
                "executor_playbook": None,
                "project_id": project_id,
                "instructions": instructions,
                "playbook_content": EXECUTOR_PLAYBOOK_CONTENT
            }
    except Exception as e:
        print(f"Error in check_awx_executor: {str(e)}")
        # 500 에러 대신 200 OK로 에러 메시지 반환하여 프론트엔드 처리 용이하게
        return {
            "status": "error",
            "message": str(e)
        }

# ==================== 인증 관련 엔드포인트 ====================

@app.get("/api/auth/keycloak-config")
async def get_keycloak_config():
    """프론트엔드에서 사용할 Keycloak 설정 반환"""
    if not KEYCLOAK_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Keycloak integration is not enabled"
        )

    return {
        "enabled": True,
        "server_url": KEYCLOAK_SERVER_URL,
        "realm": KEYCLOAK_REALM,
        "client_id": KEYCLOAK_CLIENT_ID,
        "authorization_url": KEYCLOAK_AUTHORIZATION_URL,
        "token_url": KEYCLOAK_TOKEN_URL,
        "logout_url": KEYCLOAK_LOGOUT_URL
    }

@app.get("/api/auth/me")
async def get_me(current_user: AnsibleBuilderUser = Depends(require_keycloak_user)):
    """현재 로그인한 사용자 정보 (Keycloak SSO)"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active
    }

@app.get("/api/auth/users")
async def list_users(
    current_user: AnsibleBuilderUser = Depends(get_current_user_keycloak),
    db: Session = Depends(get_db)
):
    """사용자 목록 조회 (Admin only)"""
    users = db.query(AnsibleBuilderUser).all()
    return users

@app.delete("/api/auth/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: AnsibleBuilderUser = Depends(get_current_user_keycloak),
    db: Session = Depends(get_db)
):
    """사용자 삭제 (Admin only)"""
    user = db.query(AnsibleBuilderUser).filter(AnsibleBuilderUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    username = user.username
    db.delete(user)
    db.commit()

    log_action(db, current_user, "DELETE", "user", user_id, f"Deleted user: {username}")

    return {"message": f"User {username} deleted successfully"}

# ==================== AWX OIDC Redirect ====================

@app.get("/api/awx/oidc-redirect")
async def awx_oidc_redirect(job_url: str):
    """
    AWX OIDC 인증을 통한 Job 페이지 리디렉션

    사용자를 AWX OIDC 로그인으로 리디렉션한 후 Job 페이지로 이동
    """
    from fastapi.responses import HTMLResponse
    from urllib.parse import unquote

    # URL 디코딩 (encodeURIComponent로 인코딩된 %23 -> # 변환)
    job_url = unquote(job_url)

    # AWX URL과 Job 경로 추출
    # job_url 형식: http://192.168.64.26:30000/#/jobs/playbook/123
    awx_base_url = AWX_URL  # http://192.168.64.26:30000

    # Job URL에서 해시 경로 추출
    if '#' in job_url:
        job_path = job_url.split('#')[1]  # /jobs/playbook/123
    else:
        job_path = '/home'  # 기본값

    # OIDC 로그인 후 Job 페이지로 리디렉션하는 HTML 페이지 생성
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AWX 로그인 중...</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .container {{
                text-align: center;
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 10px;
                backdrop-filter: blur(10px);
            }}
            .spinner {{
                border: 5px solid rgba(255, 255, 255, 0.3);
                border-top: 5px solid white;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            h1 {{ margin: 0 0 20px 0; }}
            p {{ margin: 10px 0; opacity: 0.9; }}
        </style>
    </head>
    <body>
        <div class="container" id="loading">
            <h1>🔐 AWX 로그인 확인 중...</h1>
            <div class="spinner"></div>
            <p>AWX 인증 상태를 확인하고 있습니다.</p>
            <p>잠시만 기다려주세요...</p>
        </div>
        <div class="container" id="redirect-info" style="display:none;">
            <h1>✅ Job이 실행되었습니다!</h1>
            <p style="margin: 20px 0;">AWX에서 Job을 확인하려면:</p>
            <ol style="text-align: left; display: inline-block; margin: 20px auto;">
                <li>AWX에 OIDC로 로그인하세요</li>
                <li>로그인 후 아래 링크를 클릭하세요</li>
            </ol>
            <p style="margin-top: 30px;">
                <a href="#" id="job-link" style="
                    display: inline-block;
                    background: white;
                    color: #667eea;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin-top: 10px;
                ">Job 페이지로 이동</a>
            </p>
            <p style="margin-top: 20px; font-size: 0.9em; opacity: 0.8;">
                또는 AWX에 이미 로그인되어 있다면 자동으로 리디렉션됩니다...
            </p>
        </div>

        <script>
            // AWX OIDC 로그인 페이지로 리디렉션
            const awxUrl = '{awx_base_url}';
            const jobPath = '{job_path}';
            const fullJobUrl = awxUrl + jobPath;

            // Job 링크 설정
            document.getElementById('job-link').href = fullJobUrl;

            // 1. 먼저 AWX API에 접근 가능한지 확인
            fetch(awxUrl + '/api/v2/me/', {{
                credentials: 'include',
                mode: 'cors'
            }})
            .then(response => {{
                if (response.ok) {{
                    // 이미 로그인됨 - 직접 Job 페이지로 이동
                    console.log('Already logged in, redirecting to job page');
                    setTimeout(() => {{
                        window.location.href = fullJobUrl;
                    }}, 1500);
                }} else {{
                    // 로그인 안 됨 - 사용자에게 안내 표시
                    console.log('Not logged in, showing instructions');
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('redirect-info').style.display = 'block';

                    // Job 링크 클릭 시 새 탭에서 AWX 열기
                    document.getElementById('job-link').onclick = function(e) {{
                        e.preventDefault();
                        window.open(fullJobUrl, '_blank');
                    }};
                }}
            }})
            .catch(error => {{
                // CORS 에러 또는 연결 실패 - 안내 표시
                console.log('Error checking auth, showing instructions');
                document.getElementById('loading').style.display = 'none';
                document.getElementById('redirect-info').style.display = 'block';

                // Job 링크 클릭 시 새 탭에서 AWX 열기
                document.getElementById('job-link').onclick = function(e) {{
                    e.preventDefault();
                    window.open(fullJobUrl, '_blank');
                }};
            }});
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)

# ==================== Frontend Static Files ====================

# Frontend 빌드 파일 경로 (Docker에서는 static, 개발환경에서는 ../frontend/frontend/dist)
FRONTEND_BUILD_DIR_DOCKER = os.path.join(os.path.dirname(__file__), "static")
FRONTEND_BUILD_DIR_DEV = os.path.join(os.path.dirname(__file__), "../frontend/frontend/dist")

# Docker 환경 우선, 개발 환경 폴백
if os.path.exists(FRONTEND_BUILD_DIR_DOCKER):
    FRONTEND_BUILD_DIR = FRONTEND_BUILD_DIR_DOCKER
elif os.path.exists(FRONTEND_BUILD_DIR_DEV):
    FRONTEND_BUILD_DIR = FRONTEND_BUILD_DIR_DEV
else:
    FRONTEND_BUILD_DIR = None

# Static files (CSS, JS 등)
if FRONTEND_BUILD_DIR and os.path.exists(FRONTEND_BUILD_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_BUILD_DIR, "assets")), name="static")

    # 루트 경로와 모든 SPA 경로는 index.html 반환
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Frontend SPA 서빙"""
        # API 경로는 건너뜀
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            raise HTTPException(status_code=404, detail="Not Found")

        # silent-check-sso.html 특별 처리
        if full_path == "silent-check-sso.html":
            return FileResponse(os.path.join(FRONTEND_BUILD_DIR, "silent-check-sso.html"))

        # vite.svg 등 정적 파일
        file_path = os.path.join(FRONTEND_BUILD_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # 나머지는 모두 index.html (SPA)
        return FileResponse(os.path.join(FRONTEND_BUILD_DIR, "index.html"))

    print(f"✓ Frontend served from: {FRONTEND_BUILD_DIR}")
else:
    print(f"⚠ Frontend build directory not found: {FRONTEND_BUILD_DIR}")

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 으로 바인딩하여 외부 접속 허용
    uvicorn.run(app, host="0.0.0.0", port=8000)