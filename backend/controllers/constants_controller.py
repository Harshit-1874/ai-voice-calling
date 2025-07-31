import logging
from services.prisma_service import PrismaService
from fastapi import HTTPException

logger = logging.getLogger(__name__)
class ConstantController:
    def __init__(self):
        self.prisma_service = PrismaService()

    async def get_constant(self, key: str):
        """Fetch a constant value by key."""
        try:
            constant = await self.prisma_service.get_constant(key)
            if not constant:
                raise HTTPException(status_code=404, detail="Constant not found")
            return {"key": constant.key, "value": constant.value}
        except Exception as e:
            logger.error(f"Error fetching constant: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
    

    async def add_constant(self, key: str, value: str):
        """Add a new constant."""
        try:
            existing_constant = await self.prisma_service.get_constant(key)
            if existing_constant:
                raise HTTPException(status_code=400, detail="Constant already exists")
            logger.info(f"Adding constant: {key} = {value}")
            constant = await self.prisma_service.set_constant(key, value)
            return {"key": constant.key, "value": constant.value}
        except Exception as e:
            logger.error(f"Error adding constant: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
    
    async def delete_constant(self, key: str):
        """Delete a constant by key."""
        try:
            constant = await self.prisma_service.get_constant(key)
            if not constant:
                raise HTTPException(status_code=404, detail="Constant not found")
            logger.info(f"Deleting constant: {key}")
            await self.prisma_service.delete_constant(key)
            return {"message": "Constant deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting constant: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
    
    async def update_constant(self, key: str, value: str):
        """Update a constant value by key."""
        try:
            constant = await self.prisma_service.get_constant(key)
            if not constant:
                raise HTTPException(status_code=404, detail="Constant not found")
            logger.info(f"Updating constant: {key} = {value}")
            updated_constant = await self.prisma_service.set_constant(key, value)
            return {"key": updated_constant.key, "value": updated_constant.value}
        except Exception as e:
            logger.error(f"Error updating constant: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        
    async def list_constants(self):
        """List all constants."""
        try:
            constants = await self.prisma_service.get_all_constants()
            return constants
        except Exception as e:
            logger.error(f"Error listing constants: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
    
    async def create_ai_config(self, data: dict):
        """Create or update AI configuration constants."""
        try:
            # Assuming data contains keys like 'VOICE', 'SYSTEM_MESSAGE', 'TEMPERATURE'
            voice = data.get("VOICE", "")
            system_message = data.get("SYSTEM_MESSAGE", "")
            temperature = data.get("TEMPERATURE", 0.5)  # Default temperature
            
            # Update or create constants
            await self.prisma_service.set_constant("VOICE", voice)
            await self.prisma_service.set_constant("SYSTEM_MESSAGE", system_message)
            await self.prisma_service.set_constant("TEMPERATURE", str(temperature))
            
            return {"message": "AI configuration updated successfully"}
        except Exception as e:
            logger.error(f"Error creating AI config: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")