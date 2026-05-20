from openapi_pyx.codegen.nodes import (
    Assign,
    AsyncMethod,
    ClientClass,
    Import,
    ImportFrom,
    ModelField,
    Module,
    Param,
    PydanticModel,
    TypeExpr,
)


def test_module_collects_imports_and_body():
    mod = Module(
        docstring="Generated.",
        imports=[Import("httpx"), ImportFrom("pydantic", ["BaseModel"])],
        body=[],
    )
    assert mod.docstring == "Generated."
    assert mod.imports[0].name == "httpx"


def test_pydantic_model_holds_fields():
    m = PydanticModel(
        name="Pet",
        fields=[
            ModelField(name="id", type_expr=TypeExpr("int"), required=True),
            ModelField(name="name", type_expr=TypeExpr("str | None"), required=False, default="None"),
        ],
    )
    assert [f.name for f in m.fields] == ["id", "name"]


def test_client_class_holds_async_methods():
    method = AsyncMethod(
        name="list_pets",
        params=[Param("self"), Param("limit", TypeExpr("int | None"), default="None", keyword_only=True)],
        return_type=TypeExpr("Pets"),
        http_method="get",
        url_template="/pets",
        query_params=[("limit", "limit")],
        path_params=[],
        header_params=[],
        body_param=None,
        response_type=TypeExpr("Pets"),
    )
    klass = ClientClass(name="PetsClient", methods=[method])
    assert klass.methods[0].http_method == "get"


def test_assign_holds_target_and_value():
    a = Assign(target="x", value="42")
    assert a.target == "x"
