import importlib
import inspect
import os
import sys
from textwrap import dedent  # remove indentation
from types import ModuleType
from typing import Dict, List, Optional

from mirix.errors import MirixToolCreateError
from mirix.functions.schema_generator import generate_schema


def derive_openai_json_schema(source_code: str, name: Optional[str] = None) -> dict:
    """Derives the OpenAI JSON schema for a given function source code.

    First, attempts to execute the source code in a custom environment with only the necessary imports.
    Then, it generates the schema from the function's docstring and signature.
    """
    try:
        # Define a custom environment with necessary imports
        env = {
            "Optional": Optional,
            "List": List,
            "Dict": Dict,
            # To support Pydantic models
            # "BaseModel": BaseModel,
            # "Field": Field,
        }
        env.update(globals())

        # print("About to execute source code...")
        exec(source_code, env)
        # print("Source code executed successfully")

        functions = [f for f in env if callable(env[f]) and not f.startswith("__")]
        if not functions:
            raise MirixToolCreateError("No callable functions found in source code")

        # print(f"Found functions: {functions}")
        func = env[functions[-1]]

        if not hasattr(func, "__doc__") or not func.__doc__:
            raise MirixToolCreateError(f"Function {func.__name__} missing docstring")

        # print("About to generate schema...")
        try:
            schema = generate_schema(func, name=name)
            # print("Schema generated successfully")
            return schema
        except TypeError as e:
            raise MirixToolCreateError(f"Type error in schema generation: {str(e)}")
        except ValueError as e:
            raise MirixToolCreateError(f"Value error in schema generation: {str(e)}")
        except Exception as e:
            raise MirixToolCreateError(f"Unexpected error in schema generation: {str(e)}")

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise MirixToolCreateError(f"Schema generation failed: {str(e)}") from e


def parse_source_code(func) -> str:
    """Parse the source code of a function and remove indendation"""
    source_code = dedent(inspect.getsource(func))
    return source_code


def get_function_from_module(module_name: str, function_name: str):
    """
    Dynamically imports a function from a specified module.

    Args:
        module_name (str): The name of the module to import (e.g., 'base').
        function_name (str): The name of the function to retrieve.

    Returns:
        Callable: The imported function.

    Raises:
        ModuleNotFoundError: If the specified module cannot be found.
        AttributeError: If the function is not found in the module.
    """
    try:
        # Dynamically import the module
        module = importlib.import_module(module_name)
        # Retrieve the function
        return getattr(module, function_name)
    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"Module '{module_name}' not found.")
    except AttributeError:
        raise AttributeError(f"Function '{function_name}' not found in module '{module_name}'.")


def get_json_schema_from_module(module_name: str, function_name: str) -> dict:
    """
    Dynamically loads a specific function from a module and generates its JSON schema.

    Args:
        module_name (str): The name of the module to import (e.g., 'base').
        function_name (str): The name of the function to retrieve.

    Returns:
        dict: The JSON schema for the specified function.

    Raises:
        ModuleNotFoundError: If the specified module cannot be found.
        AttributeError: If the function is not found in the module.
        ValueError: If the attribute is not a user-defined function.
    """
    try:
        # Dynamically import the module
        module = importlib.import_module(module_name)

        # Retrieve the function
        attr = getattr(module, function_name, None)

        # Check if it's a user-defined function
        if not (inspect.isfunction(attr) and attr.__module__ == module.__name__):
            raise ValueError(f"'{function_name}' is not a user-defined function in module '{module_name}'")

        # Generate schema (assuming a `generate_schema` function exists)
        generated_schema = generate_schema(attr)

        return generated_schema

    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"Module '{module_name}' not found.")
    except AttributeError:
        raise AttributeError(f"Function '{function_name}' not found in module '{module_name}'.")


def _get_module_source(module: ModuleType) -> str:
    """Get the source code of a module, handling PyInstaller bundles"""
    
    # Check if we're running in a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # We're in a PyInstaller bundle
        # Map the module name to a file path
        module_name = module.__name__
        
        # For function_sets modules, extract the file name
        if module_name.startswith('mirix.functions.function_sets.'):
            file_name = module_name.split('.')[-1] + '.py'
            bundled_path = os.path.join(sys._MEIPASS, 'mirix', 'functions', 'function_sets', file_name)
            
            try:
                with open(bundled_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except FileNotFoundError:
                return f"# Module source file not found: {bundled_path}"
        else:
            return f"# Module source not available for {module_name}"
    else:
        # Normal execution - use inspect.getsource
        try:
            return inspect.getsource(module)
        except OSError:
            return f"# Module source not available for {module.__name__}"


def load_function_set(module: ModuleType) -> dict:
    """Load the functions and generate schema for them, given a module object"""
    function_dict = {}

    for attr_name in dir(module):
        # Get the attribute
        attr = getattr(module, attr_name)

        # Check if it's a callable function and not a built-in or special method
        if inspect.isfunction(attr) and attr.__module__ == module.__name__:
            if attr_name in function_dict:
                raise ValueError(f"Found a duplicate of function name '{attr_name}'")

            try:
                generated_schema = generate_schema(attr)
            except Exception as e:
                import ipdb; ipdb.set_trace()
                raise e

            function_dict[attr_name] = {
                "module": _get_module_source(module),
                "python_function": attr,
                "json_schema": generated_schema,
            }

    if len(function_dict) == 0:
        raise ValueError(f"No functions found in module {module}")
    return function_dict
