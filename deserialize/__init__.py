"""A module for deserializing data to Python objects."""

#pylint: disable=unidiomatic-typecheck
#pylint: disable=protected-access
#pylint: disable=too-many-branches
#pylint: disable=wildcard-import

import functools
import typing
from typing import Any, Callable, Dict, List, Optional, Union

from deserialize.decorators import key, _get_key, parser, _get_parser
from deserialize.exceptions import DeserializeException, InvalidBaseTypeException
from deserialize.type_checks import *

__version__ = "0.3"


def deserialize(class_reference, data):
    """Deserialize data to a Python object."""

    if not isinstance(data, dict) and not isinstance(data, list):
        raise InvalidBaseTypeException("Only lists and dictionaries are supported as base raw data types")

    return _deserialize(class_reference, data)


def _deserialize(class_reference, data):
    """Deserialize data to a Python object, but allow base types"""

    # Shortcut out if we have already got the matching type.
    if not isinstance(class_reference, typing._GenericAlias) and isinstance(data, class_reference):
        return data

    if isinstance(data, dict):
        return _deserialize_dict(class_reference, data)

    if isinstance(data, list):
        return _deserialize_list(class_reference, data)

    raise InvalidBaseTypeException(f"Cannot deserialize '{type(data)}' to '{class_reference}'")



def _deserialize_list(class_reference, list_data):

    if not isinstance(list_data, list):
        raise DeserializeException(f"Cannot deserialize '{type(list_data)}' as a list.")

    if not is_list(class_reference):
        raise DeserializeException(f"Cannot deserialize a list to '{class_reference}'")

    list_content_type_value = list_content_type(class_reference)

    output = []

    for item in list_data:
        deserialized = _deserialize(list_content_type_value, item)
        output.append(deserialized)

    return output


def _deserialize_dict(class_reference, data):
    """Deserialize a dictionary to a Python object."""

    hints = typing.get_type_hints(class_reference)

    if len(hints) == 0:
        raise DeserializeException(f"Could not deserialize {data} into {class_reference} due to lack of type hints")

    class_instance = class_reference()

    for attribute_name, attribute_type in hints.items():
        property_key = _get_key(class_reference, attribute_name)
        property_value_unparsed = data.get(property_key)
        parser_function = _get_parser(class_reference, property_key)
        property_value = parser_function(property_value_unparsed)
        property_type = type(property_value)

        # Check for optionals first. We check if it's None, finish if so.
        # Otherwise we can hoist out the type and continue
        if is_optional(attribute_type):
            if property_value is None:
                setattr(class_instance, attribute_name, None)
                continue
            else:
                attribute_type = optional_content_type(attribute_type)

        # If the types match straight up, we can set and continue
        if property_type == attribute_type:
            setattr(class_instance, attribute_name, property_value)
            continue

        # Check if we have something we need to parse further or not.
        # If it is a base type (i.e. not a wrapper of some kind), then we can
        # go ahead and parse it directly without needing to iterate in any way.
        if is_base_type(attribute_type):
            custom_type_instance = _deserialize(attribute_type, property_value)
            setattr(class_instance, attribute_name, custom_type_instance)
            continue

        # Lists and dictionaries remain
        if is_list(attribute_type):
            setattr(class_instance, attribute_name, _deserialize_list(attribute_type, property_value))
            continue

        if is_dict(attribute_type):
            # If there are no values, then the types automatically do match
            if len(property_value) == 0:
                setattr(class_instance, attribute_name, property_value)
                continue

            key_type, value_type = dict_content_types(attribute_type)

            result = {}

            for item_key, item_value in property_value.items():

                if type(item_key) != key_type:
                    raise DeserializeException(f"Key '{item_key}' is type '{type(item_key)}' not '{key_type}'")

                # If the types match, we can just set it and move on
                if type(item_value) == value_type:
                    result[item_key] = item_value
                    continue

                # We have to deserialize
                item_deserialized = _deserialize(value_type, item_value)
                result[item_key] = item_deserialized

            setattr(class_instance, attribute_name, result)
            continue

        raise DeserializeException(f"Unexpected type '{property_type}' for attribute '{attribute_name}'. Expected '{attribute_type}'")

    return class_instance
