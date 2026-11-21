
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr, Field
from app.auth import router as auth_router
from app.clients import router as clients_router


app = FastAPI(
    title="FreelanceFlow API",
    description="Backend API for managing freelance projects",
    version="1.0.0",
)


# -------------------------
# PYDANTIC MODELS
# -------------------------

class Client(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    company: str = Field(min_length=2, max_length=100)


class Project(BaseModel):
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(min_length=2, max_length=550)
    budget: float = Field(gt=0)
    client_id: int = Field(gt=0)


# -------------------------
# GENERAL ROUTES
# -------------------------

@app.get("/")
def home():
    return {
        "message": "Welcome to FreelanceFlow API"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/about")
def about():
    return {
        "project": "FreelanceFlow",
        "developer": "Your Name",
        "version": "1.0.0",
        "status": "in development"
    }


# -------------------------
# CLIENT ROUTES
# -------------------------

@app.post("/clients", status_code=201)
def create_client(client: Client):
    return {
        "message": "Client created successfully",
        "client": client
    }


@app.get("/clients/{client_id}")
def get_client(
    client_id: int,
    include_projects: bool = False
):
    return {
        "client_id": client_id,
        "include_projects": include_projects,
        "message": "Client retrieved successfully"
    }


# -------------------------
# PROJECT ROUTES
# -------------------------

@app.post("/projects", status_code=201)
def create_project(project: Project):
    return {
        "message": "Project created successfully",
        "project": project
    }


@app.get("/projects")
def list_projects(status: str | None = None):
    return {
        "message": "Projects retrieved",
        "filter_status": status
    }


@app.get("/projects/{project_id}")
def get_project(project_id: int):
    return {
        "project_id": project_id,
        "message": f"Project {project_id} retrieved successfully"
    }

app.include_router(auth_router)
app.include_router(clients_router)