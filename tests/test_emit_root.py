from pathlib import Path

from openapi_pyx.codegen.emit_root import emit_root_module
from openapi_pyx.codegen.render import render_module
from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.transform.lowerer import lower_components
from openapi_pyx.transform.operations import build_document
from openapi_pyx.transform.resolver import build_schema_index

FIXTURES = Path(__file__).parent / "fixtures"


def _emit_root() -> str:
    spec = load_spec(FIXTURES / "petstore.yaml")
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)
    return render_module(emit_root_module(doc))


def test_root_imports_each_subclient():
    src = _emit_root()
    assert "from .clients.pets import PetsClient" in src


def test_root_class_exposes_subclient_attr():
    src = _emit_root()
    assert "class Client:" in src
    assert "self.pets = PetsClient(self._http)" in src
    assert "async def __aenter__" in src
    assert "async def __aexit__" in src
