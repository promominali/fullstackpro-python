from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..deps import authenticated_user_dep
from ..db import get_db
from ..models import Todo


templates = Jinja2Templates(directory="app/templates")

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(authenticated_user_dep),
):
    todos = (
        db.query(Todo)
        .filter(Todo.user_id == current_user.id)
        .order_by(Todo.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": current_user, "todos": todos},
    )


@router.post("/todos")
async def add_todo(
    title: str = Form(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(authenticated_user_dep),
):
    todo = Todo(user_id=current_user.id, title=title, description=description)
    db.add(todo)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@router.post("/todos/{todo_id}/toggle")
async def toggle_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(authenticated_user_dep),
):
    todo = (
        db.query(Todo)
        .filter(Todo.id == todo_id, Todo.user_id == current_user.id)
        .first()
    )
    if todo is not None:
        todo.is_done = not todo.is_done
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@router.post("/todos/{todo_id}/delete")
async def delete_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(authenticated_user_dep),
):
    todo = (
        db.query(Todo)
        .filter(Todo.id == todo_id, Todo.user_id == current_user.id)
        .first()
    )
    if todo is not None:
        db.delete(todo)
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
