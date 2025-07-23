import logging
from fastapi import APIRouter, WebSocket, Request, HTTPException, Query
from controllers.constants_controller import ConstantController
from services.prisma_service import PrismaService

logger = logging.getLogger(__name__)
router = APIRouter()

constant_controller = ConstantController()

@router.get("/constants/{key}", response_model=dict)
async def get_constant(key: str):
    return await constant_controller.get_constant(key)

@router.post("/constants/add", response_model=dict)
async def add_constant(request: Request):
    data = await request.json()
    return await constant_controller.add_constant(key=data["key"], value=data["value"])

@router.delete("/constants/{key}", response_model=dict)
async def delete_constant(key: str):
    return await constant_controller.delete_constant(key)

@router.put("/constants/{key}", response_model=dict)
async def update_constant(key: str, request: Request):
    data = await request.json()
    return await constant_controller.update_constant(key=key, value=data["value"])