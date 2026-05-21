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
    assert model_name("class") == "Class_"


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
