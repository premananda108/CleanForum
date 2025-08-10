import pytest
import pytest_asyncio
from models.category import Category, CategoryCreate
from models.database import db
from config import settings


@pytest_asyncio.fixture(scope="function")
async def database(monkeypatch):
    # Force test settings
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    # Connect to the DB
    await db.connect()
    await db.flush_db()
    yield
    await db.disconnect()


@pytest.mark.asyncio
async def test_create_category_success(database):
    """Test successful category creation"""
    category_data = CategoryCreate(
        name="Test Category",
        description="A test category",
        color="#ff0000"
    )
    
    category_id = await Category.create(category_data)
    assert category_id is not None
    
    # Verify category was created correctly
    category = await Category.get_by_id(category_id)
    assert category is not None
    assert category.name == "Test Category"
    assert category.description == "A test category"
    assert category.color == "#ff0000"
    assert category.post_count == 0
    assert category.is_active is True


@pytest.mark.asyncio
async def test_create_category_duplicate_name(database):
    """Test that creating a category with duplicate name fails"""
    category_data = CategoryCreate(
        name="Duplicate Category",
        description="First category"
    )
    
    # Create first category
    await Category.create(category_data)
    
    # Try to create second category with same name
    duplicate_data = CategoryCreate(
        name="Duplicate Category", 
        description="Second category"
    )
    
    with pytest.raises(ValueError, match="A category with this name already exists"):
        await Category.create(duplicate_data)


@pytest.mark.asyncio
async def test_get_category_by_name(database):
    """Test getting category by name"""
    category_data = CategoryCreate(
        name="Searchable Category",
        description="Test category for search"
    )
    
    category_id = await Category.create(category_data)
    
    # Find by name
    found_category = await Category.get_by_name("Searchable Category")
    assert found_category is not None
    assert found_category.id == category_id
    
    # Test non-existent category
    not_found = await Category.get_by_name("Non-existent Category")
    assert not_found is None


@pytest.mark.asyncio
async def test_update_post_count(database):
    """Test updating post count in category"""
    category_data = CategoryCreate(
        name="Counter Category",
        description="Test category for counting"
    )
    
    category_id = await Category.create(category_data)
    
    # Initially should be 0
    category = await Category.get_by_id(category_id)
    assert category.post_count == 0
    
    # Increase count
    await Category.update_post_count(category_id, 1)
    category = await Category.get_by_id(category_id)
    assert category.post_count == 1
    
    # Increase by multiple
    await Category.update_post_count(category_id, 5)
    category = await Category.get_by_id(category_id)
    assert category.post_count == 6
    
    # Decrease count
    await Category.update_post_count(category_id, -3)
    category = await Category.get_by_id(category_id)
    assert category.post_count == 3
    
    # Should not go below 0
    await Category.update_post_count(category_id, -10)
    category = await Category.get_by_id(category_id)
    assert category.post_count == 0


@pytest.mark.asyncio
async def test_get_all_categories(database):
    """Test getting all active categories"""
    # Initially should be empty
    categories = await Category.get_all()
    assert len(categories) == 0
    
    # Create multiple categories
    category1_data = CategoryCreate(name="Category 1", description="First")
    category2_data = CategoryCreate(name="Category 2", description="Second")
    
    await Category.create(category1_data)
    await Category.create(category2_data)
    
    # Should return both categories
    categories = await Category.get_all()
    assert len(categories) == 2
    
    category_names = {cat.name for cat in categories}
    assert category_names == {"Category 1", "Category 2"}
