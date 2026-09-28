from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(max_length=30)
    description: str = Field(max_length=300)


class CategoryRead(CategoryCreate):
    id: int


class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class EquipmentCreate(BaseModel):
    name: str = Field(max_length=50)
    code: str = Field(max_length=50)
    category_id: int = Field(gt=0)


class EquipmentRead(BaseModel):
    id: int
    name: str
    code: str
    category: CategorySummary
