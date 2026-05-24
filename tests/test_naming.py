from openapi_pyx.naming import field_name, method_name, model_name, module_name, snake_case


def test_snake_case_basic():
    assert snake_case("listPets") == "list_pets"
    assert snake_case("HTTPRequest") == "http_request"
    assert snake_case("ID") == "id"
    assert snake_case("alreadysnake") == "alreadysnake"
    assert snake_case("with-dashes") == "with_dashes"


def test_method_name_handles_python_keywords():
    assert method_name("list") == "list_"
    assert method_name("class") == "class_"


def test_model_name_pascalcase_and_keyword_safe():
    assert model_name("pet") == "Pet"
    assert model_name("pet_owner") == "PetOwner"
    # `class` is a Python keyword but `Class` (PascalCase) is a valid class name; no suffix needed.
    assert model_name("class") == "Class"
    assert model_name("license") == "License"


def test_model_name_handles_pascal_keyword_literals():
    # `None`, `True`, `False` are stored as PascalCase in keyword.kwlist;
    # the lowercase form check alone would miss them.
    assert model_name("none") == "None_"
    assert model_name("true") == "True_"
    assert model_name("false") == "False_"


def test_module_name_snake_lower():
    assert module_name("Pets") == "pets"
    assert module_name("PetOwners") == "pet_owners"


def test_field_name_preserves_builtins():
    # `id`, `type`, `format` are builtins but valid as class attribute names.
    assert field_name("id") == "id"
    assert field_name("type") == "type"
    assert field_name("format") == "format"


def test_field_name_appends_underscore_for_keywords():
    assert field_name("class") == "class_"
    assert field_name("for") == "for_"


def test_snake_case_sanitizes_non_identifier_chars():
    # GitHub uses `tag/operation` for operationIds, `+1`/`-1` for reaction fields.
    assert snake_case("repos/list-for-org") == "repos_list_for_org"
    assert snake_case("+1") == "_1"
    assert snake_case("-1") == "_1"


def test_method_name_sanitizes_slash_in_operation_id():
    assert method_name("repos/list-for-org") == "repos_list_for_org"


def test_field_name_avoids_leading_underscore_for_pydantic():
    # Pydantic v2 rejects field names starting with `_`.
    assert field_name("+1") == "f_1"
    assert field_name("-1") == "f_1"
