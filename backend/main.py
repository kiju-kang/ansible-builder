from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import subprocess
import tempfile
import os
import yaml
from datetime import datetime
import asyncio
import httpx
import json

# Database import
from database import init_db, get_db, AnsibleBuilderPlaybook, AnsibleBuilderInventory, AnsibleBuilderExecution

# Ansible 호스트 키 확인 비활성화
os.environ['ANSIBLE_HOST_KEY_CHECKING'] = 'False'

app = FastAPI(title="Ansible Playbook Builder API")

# DB 초기화
@app.on_event("startup")
def startup_event():
    init_db()
    print("Database initialized successfully")

# CORS 설정 - 모든 오리진 허용 (프로덕션에서는 특정 도메인만 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션: ["https://your-domain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 모델
class Task(BaseModel):
    name: str
    module: str
    params: Dict[str, str]

class Playbook(BaseModel):
    id: Optional[int] = None
    name: str
    hosts: str
    become: bool
    tasks: List[Task]
    created_at: Optional[str] = None

class Inventory(BaseModel):
    id: Optional[int] = None
    name: str
    content: str
    created_at: Optional[str] = None

class ExecutionRequest(BaseModel):
    playbook_id: int
    inventory_id: int
    extra_vars: Optional[Dict[str, str]] = {}

class AWXJobRequest(BaseModel):
    playbook_id: int
    inventory_id: int
    awx_url: str
    awx_username: str
    awx_password: str
    job_template_id: Optional[int] = None

# Playbook CRUD (DB 사용)
@app.post("/api/playbooks", response_model=Playbook)
async def create_playbook(playbook: Playbook, db: Session = Depends(get_db)):
    db_playbook = AnsibleBuilderPlaybook(
        name=playbook.name,
        hosts=playbook.hosts,
        become=playbook.become,
        tasks=json.dumps([task.dict() for task in playbook.tasks])
    )
    db.add(db_playbook)
    db.commit()
    db.refresh(db_playbook)
    
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
async def update_playbook(playbook_id: int, playbook: Playbook, db: Session = Depends(get_db)):
    db_playbook = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == playbook_id).first()
    if not db_playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    db_playbook.name = playbook.name
    db_playbook.hosts = playbook.hosts
    db_playbook.become = playbook.become
    db_playbook.tasks = json.dumps([task.dict() for task in playbook.tasks])
    db_playbook.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_playbook)
    
    return Playbook(
        id=db_playbook.id,
        name=db_playbook.name,
        hosts=db_playbook.hosts,
        become=db_playbook.become,
        tasks=[Task(**task) for task in json.loads(db_playbook.tasks)],
        created_at=db_playbook.created_at.isoformat()
    )

@app.delete("/api/playbooks/{playbook_id}")
async def delete_playbook(playbook_id: int, db: Session = Depends(get_db)):
    db_playbook = db.query(AnsibleBuilderPlaybook).filter(AnsibleBuilderPlaybook.id == playbook_id).first()
    if not db_playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    
    db.delete(db_playbook)
    db.commit()
    return {"message": "Playbook deleted"}

# Inventory CRUD (DB 사용)
@app.post("/api/inventories", response_model=Inventory)
async def create_inventory(inventory: Inventory, db: Session = Depends(get_db)):
    db_inventory = AnsibleBuilderInventory(
        name=inventory.name,
        content=inventory.content
    )
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)
    
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
async def delete_inventory(inventory_id: int, db: Session = Depends(get_db)):
    db_inventory = db.query(AnsibleBuilderInventory).filter(AnsibleBuilderInventory.id == inventory_id).first()
    if not db_inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    db.delete(db_inventory)
    db.commit()
    return {"message": "Inventory deleted"}

# YAML Import 기능
@app.post("/api/playbooks/import")
async def import_playbook_from_yaml(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """YAML 파일을 업로드하여 Playbook 자동 생성"""
    try:
        # 파일 읽기
        content = await file.read()
        yaml_content = content.decode('utf-8')
        
        # YAML 파싱
        parsed_yaml = yaml.safe_load(yaml_content)
        
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
                
                converted_tasks.append({
                    'name': task_name,
                    'module': module_name,
                    'params': params_dict
                })
        
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
            "message": f"Successfully imported playbook with {len(converted_tasks)} tasks"
        }
        
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")
    except Exception as e:
        import traceback
        error_detail = f"Import failed: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@app.post("/api/playbooks/import-text")
async def import_playbook_from_text(yaml_text: str, db: Session = Depends(get_db)):
    """YAML 텍스트를 직접 입력하여 Playbook 자동 생성"""
    try:
        # YAML 파싱
        parsed_yaml = yaml.safe_load(yaml_text)
        
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
                
                converted_tasks.append({
                    'name': task_name,
                    'module': module_name,
                    'params': params_dict
                })
        
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
            "message": f"Successfully imported playbook with {len(converted_tasks)} tasks"
        }
        
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")
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
            task["module"]: {k: v for k, v in task["params"].items() if v}
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

@app.get("/")
async def root():
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

# AWX Integration
@app.post("/api/awx/create-template")
async def create_awx_job_template(request: AWXJobRequest, db: Session = Depends(get_db)):
    """AWX에 새로운 Job Template 생성"""
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
    
    inventory_dict = {
        "id": inventory.id,
        "content": inventory.content
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            auth = (request.awx_username, request.awx_password)
            
            # 0. 인증 테스트
            try:
                test_res = await client.get(f"{request.awx_url}/api/v2/me/", auth=auth)
                if test_res.status_code != 200:
                    raise HTTPException(status_code=401, detail=f"AWX authentication failed: {test_res.text}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Cannot connect to AWX: {str(e)}")
            
            # 1. Organization 조회
            orgs_res = await client.get(f"{request.awx_url}/api/v2/organizations/", auth=auth)
            if orgs_res.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to get organizations: {orgs_res.text}")
            orgs = orgs_res.json()
            if not orgs.get('results'):
                raise HTTPException(status_code=400, detail="No organizations found in AWX")
            org_id = orgs['results'][0]['id']
            
            # 2. 기존 Project 중 하나 사용 (Demo Project 우선)
            projects_url = f"{request.awx_url}/api/v2/projects/"
            projects_res = await client.get(projects_url, auth=auth)
            if projects_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get projects")
            
            projects = projects_res.json()
            if not projects.get('results'):
                raise HTTPException(status_code=400, detail="No projects found in AWX. Please create at least one project with playbooks first.")
            
            # Demo Project 찾기 또는 첫 번째 Project 사용
            project_id = None
            demo_playbook = None
            for proj in projects['results']:
                if 'demo' in proj['name'].lower() or 'example' in proj['name'].lower():
                    project_id = proj['id']
                    # Demo playbook 목록 가져오기
                    playbooks_url = f"{request.awx_url}/api/v2/projects/{project_id}/playbooks/"
                    pb_res = await client.get(playbooks_url, auth=auth)
                    if pb_res.status_code == 200:
                        pbs = pb_res.json()
                        if pbs:
                            demo_playbook = pbs[0]  # 첫 번째 playbook 사용
                    break
            
            if not project_id:
                # Demo Project가 없으면 첫 번째 Project 사용
                project_id = projects['results'][0]['id']
                playbooks_url = f"{request.awx_url}/api/v2/projects/{project_id}/playbooks/"
                pb_res = await client.get(playbooks_url, auth=auth)
                if pb_res.status_code == 200:
                    pbs = pb_res.json()
                    if pbs:
                        demo_playbook = pbs[0]
            
            if not demo_playbook:
                raise HTTPException(status_code=400, detail="No playbooks found in AWX projects. Please sync a project first.")
            
            # 3. Inventory 생성
            inventory_name = f"ansible_builder_{inventory_dict['id']}"
            inventories_url = f"{request.awx_url}/api/v2/inventories/"
            
            # 기존 Inventory 확인
            inv_check = await client.get(f"{inventories_url}?name={inventory_name}", auth=auth)
            if inv_check.status_code == 200 and inv_check.json().get('count', 0) > 0:
                awx_inventory_id = inv_check.json()['results'][0]['id']
                # 기존 Inventory의 Host 삭제 후 재생성
                hosts_list_url = f"{request.awx_url}/api/v2/inventories/{awx_inventory_id}/hosts/"
                existing_hosts = await client.get(hosts_list_url, auth=auth)
                if existing_hosts.status_code == 200:
                    for host in existing_hosts.json().get('results', []):
                        await client.delete(f"{request.awx_url}/api/v2/hosts/{host['id']}/", auth=auth)
            else:
                # 새 Inventory 생성
                inv_data = {
                    "name": inventory_name,
                    "description": f"Auto-created by Ansible Builder",
                    "organization": org_id
                }
                inv_res = await client.post(inventories_url, auth=auth, json=inv_data)
                if inv_res.status_code not in [200, 201]:
                    raise HTTPException(status_code=400, detail=f"Failed to create inventory: {inv_res.text}")
                awx_inventory_id = inv_res.json()['id']
            
            # Host 추가 (ansible_user 포함)
            hosts_url = f"{request.awx_url}/api/v2/inventories/{awx_inventory_id}/hosts/"
            current_group = None
            
            for line in inventory_dict['content'].split('\n'):
                line = line.strip()
                
                # 그룹 헤더 처리
                if line.startswith('[') and line.endswith(']'):
                    current_group = line[1:-1]
                    continue
                
                # 빈 줄이나 주석 스킵
                if not line or line.startswith('#'):
                    continue
                
                # Host 파싱
                parts = line.split()
                if not parts:
                    continue
                
                hostname = parts[0]
                host_vars = {}
                
                # ansible_user, ansible_port 등 파싱
                for part in parts[1:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        host_vars[key] = value
                
                host_data = {
                    "name": hostname,
                    "description": f"Auto-created from group: {current_group}" if current_group else "",
                    "enabled": True
                }
                
                if host_vars:
                    host_data["variables"] = yaml.dump(host_vars)
                
                try:
                    host_res = await client.post(hosts_url, auth=auth, json=host_data)
                    if host_res.status_code not in [200, 201]:
                        print(f"Warning: Failed to add host {hostname}: {host_res.text}")
                except Exception as e:
                    print(f"Warning: Error adding host {hostname}: {str(e)}")
            
            # 4. Credential 조회 (gaia_bot 우선 검색)
            creds_url = f"{request.awx_url}/api/v2/credentials/"
            creds_res = await client.get(creds_url, auth=auth)
            credential_id = None
            
            if creds_res.status_code == 200:
                creds = creds_res.json()
                # gaia_bot 이름으로 검색
                for cred in creds.get('results', []):
                    if 'gaia_bot' in cred.get('name', '').lower():
                        credential_id = cred['id']
                        print(f"Found gaia_bot credential: {cred['name']} (ID: {credential_id})")
                        break
                
                # gaia_bot을 못 찾으면 Machine credential 중 첫 번째 사용
                if not credential_id:
                    machine_creds_url = f"{request.awx_url}/api/v2/credentials/?credential_type=1"
                    machine_creds_res = await client.get(machine_creds_url, auth=auth)
                    if machine_creds_res.status_code == 200:
                        machine_creds = machine_creds_res.json()
                        if machine_creds.get('results'):
                            credential_id = machine_creds['results'][0]['id']
                            print(f"Using fallback credential: {machine_creds['results'][0]['name']} (ID: {credential_id})")
            
            if not credential_id:
                print("Warning: No credentials found, template will be created without credentials")
            
            # 5. Job Template 생성
            template_name = f"{playbook['name']}_{inventory['name']}"
            templates_url = f"{request.awx_url}/api/v2/job_templates/"
            
            # 기존 Template 확인
            template_check = await client.get(f"{templates_url}?name={template_name}", auth=auth)
            if template_check.status_code == 200 and template_check.json().get('count', 0) > 0:
                # 이미 존재하면 ID 반환
                existing = template_check.json()['results'][0]
                return {
                    "status": "success",
                    "template_id": existing['id'],
                    "template_name": template_name,
                    "template_url": f"{request.awx_url}/#/templates/job_template/{existing['id']}",
                    "message": f"Job Template '{template_name}' already exists"
                }
            
            template_data = {
                "name": template_name,
                "description": f"Auto-created: {playbook['name']} on {inventory['name']} using gaia_bot",
                "job_type": "run",
                "inventory": awx_inventory_id,
                "project": project_id,
                "playbook": demo_playbook,
                "verbosity": 0,
                "ask_variables_on_launch": True,
                "extra_vars": yaml.dump({
                    "builder_playbook_name": playbook_dict['name'],
                    "builder_inventory_name": inventory.name,
                    "builder_playbook_yaml": generate_yaml(playbook_dict)
                })
            }
            
            # Credential 추가 (배열 형태)
            if credential_id:
                template_data["credentials"] = [credential_id]
                print(f"Template will use credential ID: {credential_id}")
            else:
                print("Warning: No credential found, creating template without credentials")
            
            template_res = await client.post(templates_url, auth=auth, json=template_data)
            if template_res.status_code not in [200, 201]:
                raise HTTPException(status_code=400, detail=f"Failed to create job template: {template_res.text}")
            
            template_result = template_res.json()
            
            # Template 생성 후 Credential 추가 (POST 방식이 실패할 경우 대비)
            if credential_id and template_result.get('id'):
                try:
                    # Template에 Credential 연결
                    associate_url = f"{request.awx_url}/api/v2/job_templates/{template_result['id']}/credentials/"
                    associate_data = {"id": credential_id}
                    associate_res = await client.post(associate_url, auth=auth, json=associate_data)
                    if associate_res.status_code in [200, 201, 204]:
                        print(f"Successfully associated credential {credential_id} to template {template_result['id']}")
                    else:
                        print(f"Warning: Failed to associate credential: {associate_res.text}")
                except Exception as e:
                    print(f"Warning: Error associating credential: {str(e)}")
            
            return {
                "status": "success",
                "template_id": template_result['id'],
                "template_name": template_name,
                "template_url": f"{request.awx_url}/#/templates/job_template/{template_result['id']}",
                "project_id": project_id,
                "inventory_id": awx_inventory_id,
                "inventory_url": f"{request.awx_url}/#/inventories/inventory/{awx_inventory_id}/hosts",
                "credential_id": credential_id,
                "message": f"Job Template '{template_name}' created successfully with gaia_bot credential. Playbook: {demo_playbook}"
            }
            
    except HTTPException:
        raise
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        import traceback
        error_detail = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)  # 서버 로그에 출력
        raise HTTPException(status_code=500, detail=error_detail)

@app.post("/api/awx/launch")
async def launch_awx_job(request: AWXJobRequest):
    """AWX에 Job Template 실행 요청"""
    if request.playbook_id not in playbooks_db:
        raise HTTPException(status_code=404, detail="Playbook not found")
    if request.inventory_id not in inventories_db:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    playbook = playbooks_db[request.playbook_id]
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            auth = (request.awx_username, request.awx_password)
            
            if not request.job_template_id:
                raise HTTPException(status_code=400, detail="Job Template ID is required")
            
            # Job Template 실행
            launch_url = f"{request.awx_url}/api/v2/job_templates/{request.job_template_id}/launch/"
            
            # Playbook YAML 생성
            playbook_yaml = generate_yaml(playbook_dict)
            
            # AWX Job 실행 요청
            job_data = {
                "extra_vars": {
                    "playbook_content": playbook_yaml
                }
            }
            
            response = await client.post(launch_url, auth=auth, json=job_data)
            
            if response.status_code not in [200, 201]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"AWX job launch failed: {response.text}"
                )
            
            job_result = response.json()
            
            return {
                "status": "success",
                "awx_job_id": job_result.get("id"),
                "awx_job_url": f"{request.awx_url}/#/jobs/playbook/{job_result.get('id')}",
                "message": "Job launched successfully in AWX"
            }
            
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to AWX: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AWX integration error: {str(e)}")

@app.get("/api/awx/templates")
async def get_awx_templates(awx_url: str, awx_username: str, awx_password: str):
    """AWX Job Templates 목록 조회"""
    try:
        async with httpx.AsyncClient(verify=False) as client:
            auth = (awx_username, awx_password)
            url = f"{awx_url}/api/v2/job_templates/"
            response = await client.get(url, auth=auth)
            
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

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 으로 바인딩하여 외부 접속 허용
    uvicorn.run(app, host="0.0.0.0", port=8000)
