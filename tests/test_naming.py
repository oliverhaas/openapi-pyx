from openapi_pyx.naming import method_name, model_name, module_name, snake_case


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


def test_module_name_snake_lower():
    assert module_name("Pets") == "pets"
    assert module_name("PetOwners") == "pet_owners"
