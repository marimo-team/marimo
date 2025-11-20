from __future__ import annotations

import gc
import importlib
import pathlib
import sys
import textwrap
import types
from unittest.mock import Mock

from reload_test_utils import update_file

from marimo._ast.visitor import ImportData
from marimo._runtime.reload.autoreload import (
    ModuleDependencyFinder,
    ModuleReloader,
    StrongRef,
    append_obj,
    isinstance2,
    modules_imported_by_cell,
    safe_getattr,
    safe_hasattr,
    superreload,
    update_class,
    update_function,
    update_generic,
    update_instances,
    update_property,
)


def test_reload_function(tmp_path: pathlib.Path, py_modname: str):
    sys.path.append(str(tmp_path))
    reloader = ModuleReloader()
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )
    mod = importlib.import_module(py_modname)
    reloader.check(sys.modules, reload=False)
    assert mod.foo() == 1
    update_file(
        py_file,
        """
        def foo():
            return 2
        """,
    )
    reloader.check(sys.modules, reload=True)
    assert mod.foo() == 2


def test_reload_module_with_error(tmp_path: pathlib.Path, py_modname: str):
    sys.path.append(str(tmp_path))
    reloader = ModuleReloader()
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )
    mod = importlib.import_module(py_modname)
    reloader.check(sys.modules, reload=False)
    assert mod.foo() == 1
    update_file(
        py_file,
        """
        import this_module_does_not_exist
        def foo():
            return 2
        """,
    )
    reloader.check(sys.modules, reload=True)

    assert str(py_file) in reloader.failed
    # module is still in sys.modules ...
    assert py_modname in sys.modules
    # ... but it's basically empty
    assert not hasattr(mod, "foo")


def test_reload_module_with_syntax_error(
    tmp_path: pathlib.Path, py_modname: str
):
    sys.path.append(str(tmp_path))
    reloader = ModuleReloader()
    py_file = tmp_path / pathlib.Path(py_modname + ".py")
    py_file.write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        )
    )
    mod = importlib.import_module(py_modname)
    reloader.check(sys.modules, reload=False)
    assert mod.foo() == 1
    update_file(
        py_file,
        """
        t h _ i s is in va lid python
        """,
    )
    reloader.check(sys.modules, reload=True)

    assert str(py_file) in reloader.failed
    # module is still in sys.modules ...
    assert py_modname in sys.modules
    # ... but it's basically empty
    assert not hasattr(mod, "foo")


class TestModuleDependencyFinder:
    def test_dependencies_isolated(self):
        from tests._runtime.reload.reload_data import a, b, c, d

        finder = ModuleDependencyFinder()
        a_deps = set(list(finder.find_dependencies(a, excludes=set()).keys()))
        b_deps = set(list(finder.find_dependencies(b, excludes=set()).keys()))
        c_deps = set(list(finder.find_dependencies(c, excludes=set()).keys()))
        d_deps = set(list(finder.find_dependencies(d, excludes=set()).keys()))

        assert a_deps == set(["__main__", "reload_data", "reload_data.c"])
        assert b_deps == set(["__main__", "reload_data", "reload_data.d"])
        assert c_deps == set(["__main__"])
        assert d_deps == set(["__main__"])

    def test_dependencies_cached(self):
        from tests._runtime.reload.reload_data import a

        finder = ModuleDependencyFinder()
        assert not finder.cached(a)

        finder.find_dependencies(a, excludes=set())
        assert finder.cached(a)

        finder.evict_from_cache(a)
        assert not finder.cached(a)

    def test_dependencies_module_without_file(self):
        """Test handling modules without __file__ attribute"""
        finder = ModuleDependencyFinder()
        mod = types.ModuleType("test_no_file")
        deps = finder.find_dependencies(mod, excludes=set())
        assert deps == {}
        assert not finder.cached(mod)

    def test_dependencies_module_with_syntax_error(
        self, tmp_path: pathlib.Path, py_modname: str
    ):
        """Test handling modules that have syntax errors"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text("x = 1")
        mod = importlib.import_module(py_modname)

        finder = ModuleDependencyFinder()
        # First call should work
        deps = finder.find_dependencies(mod, excludes=set())
        assert finder.cached(mod)

        # Introduce syntax error
        update_file(py_file, "invalid python +++")
        finder.evict_from_cache(mod)

        # Should return empty dict on syntax error
        deps = finder.find_dependencies(mod, excludes=set())
        assert deps == {}

    def test_dependencies_failed_module_cached(
        self, tmp_path: pathlib.Path, py_modname: str
    ):
        """Test that failed modules are added to failed cache"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        # Create a module that will fail when analyzed
        py_file.write_text("x = 1")
        mod = importlib.import_module(py_modname)

        finder = ModuleDependencyFinder()
        # Mock run_script to raise an exception other than SyntaxError
        import modulefinder

        original_run_script = modulefinder.ModuleFinder.run_script

        def failing_run_script(self, pathname):
            del self, pathname
            raise RuntimeError("Simulated failure")

        modulefinder.ModuleFinder.run_script = failing_run_script
        try:
            deps = finder.find_dependencies(mod, excludes=set())
            assert deps == {}
            assert mod.__file__ in finder._failed_module_filenames

            # Second call should use failed cache
            deps2 = finder.find_dependencies(mod, excludes=set())
            assert deps2 == {}
        finally:
            modulefinder.ModuleFinder.run_script = original_run_script


class TestSafeGetAttr:
    """Tests for safe_getattr and safe_hasattr functions"""

    def test_safe_getattr_normal(self):
        """Test safe_getattr with normal attribute access"""
        mod = types.ModuleType("test")
        mod.attr = "value"
        assert safe_getattr(mod, "attr") == "value"

    def test_safe_getattr_missing_with_default(self):
        """Test safe_getattr with missing attribute and default"""
        mod = types.ModuleType("test")
        assert safe_getattr(mod, "missing", "default") == "default"

    def test_safe_getattr_missing_no_default(self):
        """Test safe_getattr with missing attribute and no default"""
        mod = types.ModuleType("test")
        assert safe_getattr(mod, "missing") is None

    def test_safe_getattr_module_not_found(self):
        """Test safe_getattr handling ModuleNotFoundError"""

        # Create a mock object that raises ModuleNotFoundError on getattr
        class MockModule:
            def __getattribute__(self, name):
                if name != "__class__":
                    raise ModuleNotFoundError("test error")
                return super().__getattribute__(name)

        mock = MockModule()
        result = safe_getattr(mock, "any_attr", "fallback")
        assert result == "fallback"

    def test_safe_hasattr_normal(self):
        """Test safe_hasattr with normal attribute"""
        mod = types.ModuleType("test")
        mod.attr = "value"
        assert safe_hasattr(mod, "attr") is True
        assert safe_hasattr(mod, "missing") is False

    def test_safe_hasattr_module_not_found(self):
        """Test safe_hasattr handling ModuleNotFoundError"""

        class MockModule:
            def __getattribute__(self, name):
                if name != "__class__":
                    raise ModuleNotFoundError("test error")
                return super().__getattribute__(name)

        mock = MockModule()
        assert safe_hasattr(mock, "any_attr") is False


class TestModulesImportedByCell:
    """Tests for modules_imported_by_cell function"""

    def test_simple_import(self):
        """Test cell with simple module import"""
        cell = Mock()
        cell.imports = [
            ImportData(module="os", definition="os", imported_symbol=None)
        ]
        sys_modules = {"os": sys.modules["os"]}

        result = modules_imported_by_cell(cell, sys_modules)
        assert result == {"os"}

    def test_from_import(self):
        """Test cell with from...import statement"""
        cell = Mock()
        cell.imports = [
            ImportData(
                module="os", definition="path", imported_symbol="os.path"
            )
        ]
        sys_modules = {
            "os": sys.modules["os"],
            "os.path": sys.modules["os.path"],
        }

        result = modules_imported_by_cell(cell, sys_modules)
        assert "os" in result
        assert "os.path" in result

    def test_import_not_in_sys_modules(self):
        """Test that imports not in sys.modules are ignored"""
        cell = Mock()
        cell.imports = [
            ImportData(
                module="nonexistent_module",
                definition="x",
                imported_symbol=None,
            )
        ]
        sys_modules = {}

        result = modules_imported_by_cell(cell, sys_modules)
        assert result == set()

    def test_multiple_imports(self):
        """Test cell with multiple imports"""
        cell = Mock()
        cell.imports = [
            ImportData(module="sys", definition="sys", imported_symbol=None),
            ImportData(module="os", definition="os", imported_symbol=None),
            ImportData(
                module="pathlib",
                definition="Path",
                imported_symbol="pathlib.Path",
            ),
        ]
        sys_modules = {
            "sys": sys.modules["sys"],
            "os": sys.modules["os"],
            "pathlib": sys.modules["pathlib"],
            "pathlib.Path": types.ModuleType(
                "pathlib.Path"
            ),  # pretend it's a module
        }

        result = modules_imported_by_cell(cell, sys_modules)
        assert "sys" in result
        assert "os" in result
        assert "pathlib" in result


class TestModuleReloaderMethods:
    """Tests for ModuleReloader methods"""

    def test_filename_and_mtime_normal_module(
        self, tmp_path: pathlib.Path, py_modname: str
    ):
        """Test filename_and_mtime with normal module"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text("x = 1")
        mod = importlib.import_module(py_modname)

        reloader = ModuleReloader()
        result = reloader.filename_and_mtime(mod)

        assert result is not None
        assert result.name == str(py_file)
        assert result.mtime > 0

    def test_filename_and_mtime_no_file(self):
        """Test filename_and_mtime with module without __file__"""
        mod = types.ModuleType("test")
        reloader = ModuleReloader()
        result = reloader.filename_and_mtime(mod)
        assert result is None

    def test_filename_and_mtime_builtin(self):
        """Test filename_and_mtime with builtin module"""
        reloader = ModuleReloader()
        result = reloader.filename_and_mtime(sys.modules["sys"])
        assert result is None

    def test_filename_and_mtime_main_module(self):
        """Test filename_and_mtime with __main__ module"""
        mod = types.ModuleType("__main__")
        mod.__file__ = "/tmp/test.py"
        reloader = ModuleReloader()
        result = reloader.filename_and_mtime(mod)
        assert result is None

    def test_cell_uses_stale_modules_true(self):
        """Test cell_uses_stale_modules returns True for stale modules"""
        reloader = ModuleReloader()
        reloader.stale_modules = {"os", "sys"}

        cell = Mock()
        cell.imports = [
            ImportData(module="os", definition="os", imported_symbol=None)
        ]

        result = reloader.cell_uses_stale_modules(cell)
        assert result is True

    def test_cell_uses_stale_modules_false(self):
        """Test cell_uses_stale_modules returns False for fresh modules"""
        reloader = ModuleReloader()
        reloader.stale_modules = {"some_other_module"}

        cell = Mock()
        cell.imports = [
            ImportData(module="os", definition="os", imported_symbol=None)
        ]

        result = reloader.cell_uses_stale_modules(cell)
        assert result is False

    def test_check_reload_clears_stale_modules(
        self, tmp_path: pathlib.Path, py_modname: str
    ):
        """Test that check with reload=True clears stale_modules"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text("x = 1")
        mod = importlib.import_module(py_modname)

        reloader = ModuleReloader()
        reloader.check(sys.modules, reload=False)

        # Modify the file
        update_file(py_file, "x = 2")

        # Check should mark as stale
        reloader.check(sys.modules, reload=False)
        assert py_modname in reloader.stale_modules

        # Reload should clear stale modules
        reloader.check(sys.modules, reload=True)
        assert len(reloader.stale_modules) == 0


class TestUpdateFunctions:
    """Tests for update_* functions"""

    def test_update_function_code(self):
        """Test that update_function updates function code"""

        def old_func():
            return 1

        def new_func():
            return 2

        update_function(old_func, new_func)
        # After update, old_func should have new_func's code
        assert old_func() == 2

    def test_update_function_defaults(self):
        """Test that update_function updates default arguments"""

        def old_func(x=1):
            return x

        def new_func(x=2):
            return x

        update_function(old_func, new_func)
        assert old_func() == 2

    def test_update_class_methods(self):
        """Test that update_class updates class methods"""

        class OldClass:
            def method(self):
                return 1

        class NewClass:
            def method(self):
                return 2

        update_class(OldClass, NewClass)
        instance = OldClass()
        assert instance.method() == 2

    def test_update_class_removes_obsolete_attributes(self):
        """Test that update_class removes attributes not in new class"""

        class OldClass:
            old_attr = 1
            kept_attr = 2

        class NewClass:
            kept_attr = 3
            new_attr = 4

        update_class(OldClass, NewClass)
        assert not hasattr(OldClass, "old_attr")
        assert OldClass.kept_attr == 3
        assert OldClass.new_attr == 4

    def test_update_instances(self):
        """Test that update_instances updates existing instances"""

        class OldClass:
            def method(self):
                return 1

        instance = OldClass()
        assert instance.method() == 1

        class NewClass:
            def method(self):
                return 2

        # Update instances to use new class
        update_instances(OldClass, NewClass)

        # Existing instance should now use NewClass
        assert instance.__class__ is NewClass
        assert instance.method() == 2

    def test_update_property(self):
        """Test that update_property updates property get/set/del"""
        get_value = [1]

        class OldClass:
            @property
            def prop(self):
                return get_value[0]

        class NewClass:
            @property
            def prop(self):
                return get_value[0] * 2

        old_prop = OldClass.prop
        new_prop = NewClass.prop

        update_property(old_prop, new_prop)

        # After update, old property should behave like new
        instance = OldClass()
        assert instance.prop == 2

    def test_update_generic_function(self):
        """Test update_generic delegates to update_function"""

        def old_func():
            return 1

        def new_func():
            return 2

        result = update_generic(old_func, new_func)
        assert result is True
        assert old_func() == 2

    def test_update_generic_class(self):
        """Test update_generic delegates to update_class"""

        class OldClass:
            value = 1

        class NewClass:
            value = 2

        result = update_generic(OldClass, NewClass)
        assert result is True
        assert OldClass.value == 2

    def test_update_generic_unsupported_type(self):
        """Test update_generic returns False for unsupported types"""
        result = update_generic("string", "another")
        assert result is False

        result = update_generic(123, 456)
        assert result is False


class TestStrongRef:
    """Tests for StrongRef class"""

    def test_strongref_holds_reference(self):
        """Test that StrongRef keeps object alive"""
        obj = {"test": "value"}
        ref = StrongRef(obj)

        # Clear original reference
        del obj
        gc.collect()

        # StrongRef should still hold the object
        assert ref() == {"test": "value"}

    def test_strongref_callable(self):
        """Test that StrongRef can be called to get object"""
        obj = [1, 2, 3]
        ref = StrongRef(obj)
        assert ref() is obj


class TestAppendObj:
    """Tests for append_obj function"""

    def test_append_obj_in_module(self):
        """Test append_obj adds object from same module"""
        mod = types.ModuleType("test_mod")

        class TestClass:
            pass

        TestClass.__module__ = "test_mod"
        mod.__name__ = "test_mod"

        d = {}
        result = append_obj(mod, d, "TestClass", TestClass)

        assert result is True
        assert ("test_mod", "TestClass") in d
        assert len(d[("test_mod", "TestClass")]) == 1

    def test_append_obj_not_in_module(self):
        """Test append_obj ignores objects from different module"""
        mod = types.ModuleType("test_mod")
        mod.__name__ = "test_mod"

        class TestClass:
            pass

        TestClass.__module__ = "other_mod"

        d = {}
        result = append_obj(mod, d, "TestClass", TestClass)

        assert result is False
        assert ("test_mod", "TestClass") not in d

    def test_append_obj_no_module_attr(self):
        """Test append_obj with object without __module__"""
        mod = types.ModuleType("test_mod")
        mod.__name__ = "test_mod"

        obj = "string"  # strings don't have __module__

        d = {}
        result = append_obj(mod, d, "obj", obj)

        assert result is False

    def test_append_obj_multiple_objects(self):
        """Test append_obj with multiple objects"""
        mod = types.ModuleType("test_mod")
        mod.__name__ = "test_mod"

        class TestClass1:
            pass

        class TestClass2:
            pass

        TestClass1.__module__ = "test_mod"
        TestClass2.__module__ = "test_mod"

        d = {}
        append_obj(mod, d, "TestClass1", TestClass1)
        append_obj(mod, d, "TestClass2", TestClass2)

        assert ("test_mod", "TestClass1") in d
        assert ("test_mod", "TestClass2") in d


class TestIsinstance2:
    """Tests for isinstance2 helper function"""

    def test_isinstance2_both_match(self):
        """Test isinstance2 when both are of the type"""
        assert isinstance2(int, int, type) is True
        assert isinstance2(str, str, type) is True

    def test_isinstance2_first_not_match(self):
        """Test isinstance2 when first is not of the type"""
        assert isinstance2("string", int, type) is False

    def test_isinstance2_second_not_match(self):
        """Test isinstance2 when second is not of the type"""
        assert isinstance2(int, "string", type) is False

    def test_isinstance2_neither_match(self):
        """Test isinstance2 when neither is of the type"""
        assert isinstance2("string", 123, type) is False

    def test_isinstance2_with_functions(self):
        """Test isinstance2 with function type"""

        def func1():
            pass

        def func2():
            pass

        assert isinstance2(func1, func2, types.FunctionType) is True
        assert isinstance2(func1, "not_func", types.FunctionType) is False


class TestSuperreload:
    """Tests for superreload function"""

    def test_superreload_basic(self, tmp_path: pathlib.Path, py_modname: str):
        """Test basic superreload functionality"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text("value = 1")

        mod = importlib.import_module(py_modname)
        assert mod.value == 1

        # Update module
        update_file(py_file, "value = 2")

        old_objects = {}
        superreload(mod, old_objects)

        assert mod.value == 2

    def test_superreload_tracks_old_objects(
        self, tmp_path: pathlib.Path, py_modname: str
    ):
        """Test that superreload tracks old objects"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text(
            textwrap.dedent("""
            class MyClass:
                value = 1

            def my_func():
                return 1
            """)
        )

        mod = importlib.import_module(py_modname)
        MyClass = mod.MyClass
        my_func = mod.my_func

        old_objects = {}
        superreload(mod, old_objects)

        # Should have tracked the class and function
        assert (py_modname, "MyClass") in old_objects
        assert (py_modname, "my_func") in old_objects

    def test_superreload_with_error_raises(
        self, tmp_path: pathlib.Path, py_modname: str
    ):
        """Test that superreload raises on error"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text("value = 1")

        mod = importlib.import_module(py_modname)

        # Introduce syntax error
        update_file(py_file, "invalid python +++")

        import pytest

        with pytest.raises(SyntaxError):
            superreload(mod, {})

    def test_superreload_updates_existing_objects(
        self, tmp_path: pathlib.Path, py_modname: str
    ):
        """Test that superreload updates existing class instances"""
        sys.path.append(str(tmp_path))
        py_file = tmp_path / pathlib.Path(py_modname + ".py")
        py_file.write_text(
            textwrap.dedent("""
            class MyClass:
                def method(self):
                    return 1
            """)
        )

        mod = importlib.import_module(py_modname)
        instance = mod.MyClass()
        assert instance.method() == 1

        # Update the module
        update_file(
            py_file,
            """
            class MyClass:
                def method(self):
                    return 2
            """,
        )

        old_objects = {}
        superreload(mod, old_objects)
        superreload(mod, old_objects)  # second reload uses old_objects

        # Instance should now use updated method
        assert instance.method() == 2
