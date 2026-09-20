from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
)
from app.schemas.user import LoginRequest, RefreshRequest, TokenResponse, UserCreate, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from app.core.security import decode_token

    payload = decode_token(request.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user_id = payload.get("sub")
    from sqlalchemy import select

    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    return {"message": "Logged out successfully"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await auth_service.get_user_by_username(db, user_data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    existing_email = await auth_service.get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = await auth_service.create_user(db, user_data)
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select

    from app.models.user import User

    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/change-password")
async def change_password(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    old_password = body.get("old_password")
    new_password = body.get("new_password")
    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="old_password and new_password are required")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")
    user = await auth_service.authenticate_user(db, current_user["username"], old_password)
    if not user:
        raise HTTPException(status_code=401, detail="原密码错误")
    from sqlalchemy import select

    from app.models.user import User

    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    db_user = result.scalar_one_or_none()
    db_user.hashed_password = get_password_hash(new_password)
    await db.commit()
    return {"message": "密码修改成功"}
