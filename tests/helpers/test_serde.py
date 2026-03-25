"""Unit tests for serde.py serialization helpers."""

import pytest
from dataclasses import dataclass
from typing import Any

from kuhl_haus.mdp.helpers.serde import to_dict


# Test fixtures


@pytest.fixture
def simple_object():
    """Create a simple object with basic attributes."""
    class SimpleClass:
        def __init__(self):
            self.name = "test"
            self.value = 42
            self.flag = True
    return SimpleClass()


@pytest.fixture
def nested_object():
    """Create an object with nested class instances."""
    class Inner:
        def __init__(self):
            self.inner_value = "nested"
            self.inner_number = 100

    class Outer:
        def __init__(self):
            self.outer_value = "outer"
            self.inner = Inner()

    return Outer()


@pytest.fixture
def deeply_nested_object():
    """Create an object with multiple levels of nesting."""
    class Level3:
        def __init__(self):
            self.level = 3
            self.data = "deepest"

    class Level2:
        def __init__(self):
            self.level = 2
            self.child = Level3()

    class Level1:
        def __init__(self):
            self.level = 1
            self.child = Level2()

    return Level1()


@pytest.fixture
def object_with_list():
    """Create an object containing a list of nested objects."""
    class Item:
        def __init__(self, name: str, value: int):
            self.name = name
            self.value = value

    class Container:
        def __init__(self):
            self.items = [Item("first", 1), Item("second", 2), Item("third", 3)]
            self.name = "container"

    return Container()


@pytest.fixture
def object_with_mixed_types():
    """Create an object with various attribute types."""
    class MixedClass:
        def __init__(self):
            self.string_val = "text"
            self.int_val = 123
            self.float_val = 45.67
            self.bool_val = False
            self.none_val = None
            self.list_val = [1, 2, 3]
            self.dict_val = {"key": "value"}

    return MixedClass()


# Tests for None values


def test_to_dict_with_none_expect_none():
    # Arrange
    obj = None

    # Act
    result = to_dict(obj)

    # Assert
    assert result is None


# Tests for primitive types


@pytest.mark.parametrize("input_value,expected", [
    ("hello", "hello"),
    ("", ""),
    ("unicode: café", "unicode: café"),
])
def test_to_dict_with_string_expect_same_string(input_value, expected):
    # Arrange
    # (input_value from parametrize)

    # Act
    result = to_dict(input_value)

    # Assert
    assert result == expected
    assert isinstance(result, str)


@pytest.mark.parametrize("input_value,expected", [
    (0, 0),
    (42, 42),
    (-100, -100),
    (999999, 999999),
])
def test_to_dict_with_integer_expect_same_integer(input_value, expected):
    # Arrange
    # (input_value from parametrize)

    # Act
    result = to_dict(input_value)

    # Assert
    assert result == expected
    assert isinstance(result, int)


@pytest.mark.parametrize("input_value,expected", [
    (0.0, 0.0),
    (3.14, 3.14),
    (-2.5, -2.5),
    (1.23456789, 1.23456789),
])
def test_to_dict_with_float_expect_same_float(input_value, expected):
    # Arrange
    # (input_value from parametrize)

    # Act
    result = to_dict(input_value)

    # Assert
    assert result == expected
    assert isinstance(result, float)


@pytest.mark.parametrize("input_value,expected", [
    (True, True),
    (False, False),
])
def test_to_dict_with_boolean_expect_same_boolean(input_value, expected):
    # Arrange
    # (input_value from parametrize)

    # Act
    result = to_dict(input_value)

    # Assert
    assert result == expected
    assert isinstance(result, bool)


# Tests for lists and tuples


def test_to_dict_with_empty_list_expect_empty_list():
    # Arrange
    obj = []

    # Act
    result = to_dict(obj)

    # Assert
    assert result == []
    assert isinstance(result, list)


def test_to_dict_with_list_of_primitives_expect_same_list():
    # Arrange
    obj = [1, "two", 3.0, True, None]

    # Act
    result = to_dict(obj)

    # Assert
    assert result == [1, "two", 3.0, True, None]
    assert isinstance(result, list)


def test_to_dict_with_nested_list_expect_flattened_structure():
    # Arrange
    obj = [[1, 2], [3, 4], [5, [6, 7]]]

    # Act
    result = to_dict(obj)

    # Assert
    assert result == [[1, 2], [3, 4], [5, [6, 7]]]
    assert isinstance(result, list)


def test_to_dict_with_tuple_expect_converted_to_list():
    # Arrange
    obj = (1, 2, 3)

    # Act
    result = to_dict(obj)

    # Assert
    assert result == [1, 2, 3]
    assert isinstance(result, list)


def test_to_dict_with_nested_tuple_expect_converted_to_nested_list():
    # Arrange
    obj = ((1, 2), (3, 4))

    # Act
    result = to_dict(obj)

    # Assert
    assert result == [[1, 2], [3, 4]]
    assert isinstance(result, list)


def test_to_dict_with_list_of_objects_expect_list_of_dicts(object_with_list):
    # Arrange
    obj = object_with_list

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "name": "container",
        "items": [
            {"name": "first", "value": 1},
            {"name": "second", "value": 2},
            {"name": "third", "value": 3},
        ]
    }


# Tests for dictionaries


def test_to_dict_with_empty_dict_expect_empty_dict():
    # Arrange
    obj = {}

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {}
    assert isinstance(result, dict)


def test_to_dict_with_simple_dict_expect_same_dict():
    # Arrange
    obj = {"key1": "value1", "key2": 42, "key3": True}

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {"key1": "value1", "key2": 42, "key3": True}
    assert isinstance(result, dict)


def test_to_dict_with_nested_dict_expect_recursively_converted():
    # Arrange
    obj = {
        "outer": {
            "inner": {
                "deep": "value"
            }
        }
    }

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "outer": {
            "inner": {
                "deep": "value"
            }
        }
    }


def test_to_dict_with_dict_containing_objects_expect_objects_converted():
    # Arrange
    class Item:
        def __init__(self, value):
            self.value = value

    obj = {
        "item1": Item(1),
        "item2": Item(2)
    }

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "item1": {"value": 1},
        "item2": {"value": 2}
    }


# Tests for simple objects


def test_to_dict_with_simple_object_expect_dict_with_attributes(simple_object):
    # Arrange
    obj = simple_object

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "name": "test",
        "value": 42,
        "flag": True
    }
    assert isinstance(result, dict)


def test_to_dict_with_object_no_attributes_expect_empty_dict():
    # Arrange
    class EmptyClass:
        pass
    obj = EmptyClass()

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {}
    assert isinstance(result, dict)


# Tests for nested objects


def test_to_dict_with_nested_object_expect_nested_dicts(nested_object):
    # Arrange
    obj = nested_object

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "outer_value": "outer",
        "inner": {
            "inner_value": "nested",
            "inner_number": 100
        }
    }


def test_to_dict_with_deeply_nested_object_expect_fully_converted(deeply_nested_object):
    # Arrange
    obj = deeply_nested_object

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "level": 1,
        "child": {
            "level": 2,
            "child": {
                "level": 3,
                "data": "deepest"
            }
        }
    }


# Tests for mixed types


def test_to_dict_with_mixed_types_expect_all_converted(object_with_mixed_types):
    # Arrange
    obj = object_with_mixed_types

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "string_val": "text",
        "int_val": 123,
        "float_val": 45.67,
        "bool_val": False,
        "none_val": None,
        "list_val": [1, 2, 3],
        "dict_val": {"key": "value"}
    }


# Tests for special types (fallback to str)


def test_to_dict_with_set_expect_string_representation():
    # Arrange
    obj = {1, 2, 3}

    # Act
    result = to_dict(obj)

    # Assert
    assert isinstance(result, str)
    assert "1" in result
    assert "2" in result
    assert "3" in result


def test_to_dict_with_custom_type_without_dict_expect_string():
    # Arrange
    class CustomType:
        def __str__(self):
            return "custom_string"
        # No __dict__ attribute
    obj = CustomType()
    # Remove __dict__ to simulate object without it
    if hasattr(obj, '__dict__'):
        # For objects that have __dict__, we need a different approach
        # Use a type that naturally doesn't have __dict__
        obj = complex(1, 2)

    # Act
    result = to_dict(obj)

    # Assert
    assert isinstance(result, str)


# Tests for dataclasses


def test_to_dict_with_dataclass_expect_dict_conversion():
    # Arrange
    @dataclass
    class Person:
        name: str
        age: int

    obj = Person(name="Alice", age=30)

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "name": "Alice",
        "age": 30
    }


def test_to_dict_with_nested_dataclass_expect_recursive_conversion():
    # Arrange
    @dataclass
    class Address:
        street: str
        city: str

    @dataclass
    class Person:
        name: str
        address: Address

    obj = Person(name="Bob", address=Address(street="123 Main St", city="Springfield"))

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "name": "Bob",
        "address": {
            "street": "123 Main St",
            "city": "Springfield"
        }
    }


# Tests for circular references handling (edge case)


def test_to_dict_with_object_containing_none_attributes_expect_none_preserved():
    # Arrange
    class ClassWithNone:
        def __init__(self):
            self.value = None
            self.name = "test"
    obj = ClassWithNone()

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "value": None,
        "name": "test"
    }
    assert result["value"] is None


# Tests for complex real-world scenarios


def test_to_dict_with_complex_nested_structure_expect_full_conversion():
    # Arrange
    class Config:
        def __init__(self):
            self.enabled = True
            self.timeout = 30

    class Service:
        def __init__(self, name):
            self.name = name
            self.config = Config()
            self.tags = ["production", "api"]

    class Application:
        def __init__(self):
            self.services = [Service("auth"), Service("api")]
            self.metadata = {"version": "1.0", "env": "prod"}

    obj = Application()

    # Act
    result = to_dict(obj)

    # Assert
    assert result == {
        "services": [
            {
                "name": "auth",
                "config": {"enabled": True, "timeout": 30},
                "tags": ["production", "api"]
            },
            {
                "name": "api",
                "config": {"enabled": True, "timeout": 30},
                "tags": ["production", "api"]
            }
        ],
        "metadata": {"version": "1.0", "env": "prod"}
    }
