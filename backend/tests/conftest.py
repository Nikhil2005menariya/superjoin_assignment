"""
Shared fixtures for all tests.
Uses httpx.AsyncClient against a real running FastAPI app (in-process).
Qdrant and SQLite are pointed at temp paths so tests are isolated.
"""

import os
import tempfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ── Override settings before app import ──────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def patch_settings(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fkl_test")
    os.environ["QDRANT_HOST"]     = "localhost"
    os.environ["QDRANT_PORT"]     = "6333"
    os.environ["GROQ_API_KEY"]    = os.getenv("GROQ_API_KEY", "test-key")
    os.environ["FASTEMBED_CACHE_PATH"] = str(tmp / "models")
    # Point DB at temp file
    db_path = str(tmp / "test.db")
    os.environ["DATA_DIR"]   = str(tmp)
    os.environ["DB_PATH"]    = db_path
    os.environ["UPLOADS_DIR"] = str(tmp / "uploads")
    (tmp / "uploads").mkdir(exist_ok=True)
    yield


@pytest_asyncio.fixture(scope="session")
async def app():
    """Create the FastAPI app with test DB."""
    from app.config import get_settings
    get_settings.cache_clear()
    cfg = get_settings()
    cfg.db_path     = os.environ["DB_PATH"]
    cfg.data_dir    = os.environ["DATA_DIR"]
    cfg.uploads_dir = os.environ["UPLOADS_DIR"]

    from app.database.sqlite import init_db
    await init_db()

    from app.main import app as _app
    return _app


@pytest_asyncio.fixture(scope="session")
async def client(app):
    """HTTP client wired directly to the FastAPI ASGI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ── Minimal synthetic PDF fixture ─────────────────────────────────────────────
@pytest.fixture(scope="session")
def sample_pdf_path(tmp_path_factory):
    """
    Creates a minimal valid PDF with two pages of financial text.
    Does not require any external PDF library at fixture creation time.
    """
    tmp = tmp_path_factory.mktemp("pdfs")
    pdf_path = tmp / "test_doc.pdf"

    # Minimal PDF binary (page with text content)
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R 4 0 R]/Count 2>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]
/Contents 5 0 R/Resources<</Font<</F1 6 0 R>>>>>>endobj
4 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]
/Contents 7 0 R/Resources<</Font<</F1 6 0 R>>>>>>endobj
5 0 obj<</Length 200>>
stream
BT /F1 12 Tf 72 720 Td
(Delhivery Limited Annual Report FY2024) Tj T*
(Revenue for FY2024 was Rs 21302 Crore.) Tj T*
(The company serves 18793 pin codes across India.) Tj T*
(EBITDA margin improved to 4.2 percent in Q4 FY24.) Tj
ET
endstream
endobj
6 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
7 0 obj<</Length 150>>
stream
BT /F1 12 Tf 72 720 Td
(India GDP growth rate was 6.4 per cent in 2024-25.) Tj T*
(Inflation declined to 4.6 percent in FY25.) Tj T*
(Current account deficit stood at 1.2 percent of GDP.) Tj
ET
endstream
endobj
xref
0 8
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000433 00000 n
0000000685 00000 n
0000000758 00000 n
trailer<</Size 8/Root 1 0 R>>
startxref
960
%%EOF"""
    pdf_path.write_bytes(content)
    return str(pdf_path)
