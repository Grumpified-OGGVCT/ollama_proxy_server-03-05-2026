import pytest
from unittest.mock import AsyncMock, patch
from app.api.v1.routes.proxy import _select_auto_model


@pytest.fixture
def mock_db():
    return AsyncMock()


class MockMetadata:
    def __init__(self, model_name, supports_images=False, is_code_model=False, context_length=8192, priority=1):
        self.model_name = model_name
        self.supports_images = supports_images
        self.is_code_model = is_code_model
        self.context_length = context_length
        self.priority = priority


@pytest.mark.asyncio
@patch("app.crud.model_metadata_crud.get_all_metadata")
@patch("app.crud.server_crud.get_all_available_model_names")
async def test_select_auto_model_vision(mock_get_all_available, mock_get_all_metadata, mock_db):
    mock_get_all_available.return_value = ["llama2", "llava"]
    mock_get_all_metadata.return_value = [MockMetadata("llama2"), MockMetadata("llava", supports_images=True)]

    body = {"images": ["base64data"]}
    result = await _select_auto_model(mock_db, body)

    assert result == "llava"


@pytest.mark.asyncio
@patch("app.crud.model_metadata_crud.get_all_metadata")
@patch("app.crud.server_crud.get_all_available_model_names")
async def test_select_auto_model_code(mock_get_all_available, mock_get_all_metadata, mock_db):
    mock_get_all_available.return_value = ["llama2", "codellama"]
    mock_get_all_metadata.return_value = [MockMetadata("llama2"), MockMetadata("codellama", is_code_model=True)]

    body = {"prompt": "def calculate_fibonacci(n):"}
    result = await _select_auto_model(mock_db, body)

    assert result == "codellama"


@pytest.mark.asyncio
@patch("app.crud.model_metadata_crud.get_all_metadata")
@patch("app.crud.server_crud.get_all_available_model_names")
async def test_select_auto_model_standard(mock_get_all_available, mock_get_all_metadata, mock_db):
    mock_get_all_available.return_value = ["llama2"]
    mock_get_all_metadata.return_value = [MockMetadata("llama2")]

    body = {"messages": [{"role": "user", "content": "Hello world"}]}
    result = await _select_auto_model(mock_db, body)

    assert result == "llama2"


@pytest.mark.asyncio
@patch("app.crud.model_metadata_crud.get_all_metadata")
@patch("app.crud.server_crud.get_all_available_model_names")
async def test_select_auto_model_complex_message_format(mock_get_all_available, mock_get_all_metadata, mock_db):
    mock_get_all_available.return_value = ["llama2", "codellama"]
    mock_get_all_metadata.return_value = [MockMetadata("llama2"), MockMetadata("codellama", is_code_model=True)]

    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": "public static void main(String[] args)"}]}]}
    result = await _select_auto_model(mock_db, body)

    assert result == "codellama"


@pytest.mark.asyncio
@patch("app.crud.model_metadata_crud.get_all_metadata")
@patch("app.crud.server_crud.get_all_available_model_names")
async def test_select_auto_model_no_models(mock_get_all_available, mock_get_all_metadata, mock_db):
    mock_get_all_available.return_value = []
    mock_get_all_metadata.return_value = [MockMetadata("llama2")]

    body = {"prompt": "Hello"}
    result = await _select_auto_model(mock_db, body)

    assert result is None
