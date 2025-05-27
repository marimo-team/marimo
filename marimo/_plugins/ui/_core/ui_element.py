# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import base64
import copy
import random
import sys
import types
import uuid
import weakref
from dataclasses import dataclass, fields
from html import escape
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Optional,
    TypeVar,
    cast,
)

from marimo import _loggers
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType, build_ui_plugin
from marimo._plugins.ui._core import ids
from marimo._runtime.context import (
    ContextNotInitializedError,
    RuntimeContext,
    get_context,
)
from marimo._runtime.functions import Function
from marimo._types.ids import UIElementId

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._plugins.ui._impl.input import form as form_plugin

# S: Type of frontend value
#   - the initial value sent to the frontend must be of type S
#   - values received from the frontend must be of type S
S = TypeVar("S", bound=JSONType)

# T: Type of `UIElement.value`
#   - UIElement's `_convert_value` method is used to convert a frontend
#   value (of type S) to a value of type T
T = TypeVar("T")

LOGGER = _loggers.marimo_logger()


@dataclass
class Lens:
    """Track how a view of a higher-order element relates to its source

    Higher-order UI elements support lensing, ie extracting their children
    as "views". These views can be embedded in other outputs and interacted
    with.

    UI elements that are views of a higher-order element (eg, an entry of
    an array is a view of the array) have a lens object that stores the
    id of its parent UI element, and the key at which its parent stores it.
    """

    parent_id: UIElementId
    key: str


@dataclass
class InitializationArgs(Generic[S, T]):
    component_name: str
    initial_value: S
    label: Optional[str]
    on_change: Optional[Callable[[T], None]]
    args: dict[str, JSONType]
    slotted_html: str
    functions: tuple[Function[Any, Any], ...]


class MarimoConvertValueException(Exception):
    pass


@mddoc
class UIElement(Html, Generic[S, T]):
    """An HTML element with a value

    A `UIElement` is an HTML element with a value; when the value of the
    element on the page changes, the value of the UIElement is updated as well.

    This is an abstract class. `UIElement`s are responsible for mapping values
    sent by the frontend (of type S) to values expected by the Python object
    (of type T): a subclass can be made concrete by implementing the
    `_convert_value` method.

    Type Parameters:

    - S: The type of the values sent by the frontend to the kernel; must be
         JSON-serializable
    - T: The type of the UIElement's value; can be any type

    **Attributes.**

    - value: The value of the `UIElement`.

    **Methods.**

    - form: create a submittable form this `UIElement`.
    """

    _value_frontend: S
    _value: T

    # We want this to be fully random in production,
    # otherwise cached session state could use incorrect object-ids.
    # And changing object-ids are a way to force a re-render.
    #
    # This does mean that snapshotting exports in CI will produce
    # different object-ids. If this is a problem, we can allow a
    # fixed seed via an environment variable.
    _random_seed = random.Random()

    def __init__(
        self,
        component_name: str,
        initial_value: S,
        label: Optional[str],
        on_change: Optional[Callable[[T], None]],
        args: dict[str, JSONType],
        slotted_html: str = "",
        functions: tuple[Function[Any, Any], ...] = (),
    ) -> None:
        """Initialize a UIElement

        Args:
        ----
        component_name: tag name of the custom element
        initial_value: initial value of the element in the frontend
        label: markdown string, label of element
        on_change: callback, called with element's new value on change
        args: arguments that the element takes
        slotted_html: any html to slot in the custom element
        functions: any functions to register with the graph
        """
        # Validate parameters from a user
        if not isinstance(component_name, str):
            raise TypeError("component_name must be a string")
        if label is not None and not isinstance(label, str):
            raise TypeError("label must be a string or None")
        if on_change is not None and not callable(on_change):
            raise TypeError("on_change must be a callable or None")

        # arguments stored in signature order for cloning
        self._component_args = args
        self._args: InitializationArgs[S, T] = InitializationArgs(
            component_name=component_name,
            initial_value=initial_value,
            label=label,
            on_change=on_change,
            args=args,
            slotted_html=slotted_html,
            functions=functions,
        )
        self._initialized = False
        self._initialize(self._args)
        self._initialized = True

    def _initialize(
        self, initialization_args: InitializationArgs[S, T]
    ) -> None:
        """Initialize the UIElement

        Split out from __init__ so _clone() typechecks
        """
        (
            component_name,
            initial_value,
            label,
            on_change,
            args,
            slotted_html,
            functions,
        ) = (
            initialization_args.component_name,
            initialization_args.initial_value,
            initialization_args.label,
            initialization_args.on_change,
            initialization_args.args,
            initialization_args.slotted_html,
            initialization_args.functions,
        )
        # A UIElement may be a child ("lens") of another UI element.
        #
        # Set with self._register_as_view() after initialization, since parents
        # are usually created after the child is created
        self._lens: Lens | None = None

        # Random token
        #
        # Every element is annotated with a random token, which by design is
        # different every time the element is constructed (i.e., every time a
        # cell runs): this guarantees that re-running a cell that creates a UI
        # element will trigger a re-render and reset it to its initial value.
        # We need this to ensure that the element on the page is synchronized
        # with the element in the kernel.
        # We use a fixed seed so that we can reproduce the same random ids
        # across multiple runs (useful when exporting as html or in tests)
        self._random_id = str(
            uuid.UUID(int=self._random_seed.getrandbits(128))
        )

        # Stable ID
        #
        # Every element has an ID that is used for two purposes:
        #  - to synchronize multiple instances of the element on the page
        #  - to synchronize elements on the page with elements in the kernel
        #
        # IDs are stable across multiple sessions if the set of UI elements
        # created by each cell is deterministic; this fact is used to
        # optionally override the element's initial value.
        try:
            self._id = UIElementId(get_context().take_id())
        except (ids.NoIDProviderException, ContextNotInitializedError):
            self._id = UIElementId(self._random_id)

        self._ctx: RuntimeContext | None
        try:
            # cache the context in case the UI element is constructed
            # in a nested context -- so that if the UI element is accessed
            # in the root context (eg with app_result.defs["elem"].value),
            # the correct constructing context is retrieved
            self._ctx = get_context()
        except ContextNotInitializedError:
            self._ctx = None
        else:
            # When the UI element is destructed, it should be removed
            # from the UIElementRegistry (which only holds a weakref to it).
            finalizer = weakref.finalize(
                self, self._ctx.ui_element_registry.delete, self._id, id(self)
            )
            # No need to clean up the registry at program teardown
            finalizer.atexit = False

        if self._ctx is not None:
            self._ctx.ui_element_registry.register(self._id, self)
            # an Instantiate request may want us to override the initial value
            try:
                # NB: If a cell produces a non-deterministic set of
                # UI elements, a UI element may be matched with an initial
                # value that was actually for some other element
                #
                # TODO(akshayka): validate the tag-name to make sure that the
                # value is at least the right type (ie, S)
                #
                # TODO(akshayka): parametrize UIElement with an optional
                # string ID, so users can provide their own IDs to make
                # sure a mismatch never happens ...
                initial_value = cast(
                    S, self._ctx.get_ui_initial_value(self._id)
                )
            except KeyError:
                # we weren't asked to override the UI element's value
                pass

            for function in functions:
                self._ctx.function_registry.register(
                    namespace=self._id, function=function
                )
        self._initial_value_frontend = initial_value
        self._value_frontend = initial_value
        self._value = self._initial_value = self._convert_value(initial_value)
        self._on_change = on_change
        self._component_args = args

        self._inner_text = build_ui_plugin(
            component_name,
            initial_value,
            label,
            args,
            slotted_html,
        )
        text = (
            f"<marimo-ui-element object-id='{self._id}' "
            + f"random-id='{self._random_id}'>"
            + self._inner_text
            + "</marimo-ui-element>"
        )
        super().__init__(text=text)

    @abc.abstractmethod
    def _convert_value(self, value: S) -> T:
        """Converts a value from the frontend to a value for the `UIElement`

        This method must convert `value`, the JSON-decoded value sent by the
        frontend, to a value of type `T` for the `UIElement`.
        """
        pass

    def _register_as_view(self, parent: UIElement[Any, Any], key: str) -> None:
        """Register this element as a view of `parent`."""
        self._lens = Lens(parent_id=parent._id, key=key)

    @property
    def value(self) -> T:
        """The element's current value."""
        if self._ctx is None:
            return self._value

        if (
            self._ctx.execution_context is not None
            and not self._ctx.execution_context.setting_element_value
            and (
                self._ctx.execution_context.cell_id
                == self._ctx.ui_element_registry.get_cell(self._id)
            )
        ):
            raise RuntimeError(
                "Accessing the value of a UIElement in the cell that created "
                "it is not allowed. Fix: move the value access to another "
                "cell."
            )
        return self._value

    @value.setter
    def value(self, value: T) -> None:
        del value
        raise RuntimeError(
            "Setting the value of a UIElement is not allowed. "
            "If you need to imperatively set the value of a UIElement, "
            "consider using mo.state()."
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "on_change":
            raise RuntimeError(
                "Setting the on_change handler of a UIElement is not allowed. "
                "You must set the on_change in the constructor."
            )
        super().__setattr__(name, value)

    @mddoc
    def form(
        self,
        label: str = "",
        *,
        bordered: bool = True,
        loading: bool = False,
        submit_button_label: str = "Submit",
        submit_button_tooltip: Optional[str] = None,
        submit_button_disabled: bool = False,
        clear_on_submit: bool = False,
        show_clear_button: bool = False,
        clear_button_label: str = "Clear",
        clear_button_tooltip: Optional[str] = None,
        validate: Optional[
            Callable[[Optional[JSONType]], Optional[str]]
        ] = None,
        on_change: Optional[Callable[[Optional[T]], None]] = None,
    ) -> form_plugin[S, T]:
        """Create a submittable form out of this `UIElement`.

        Creates a form that gates submission of a `UIElement`'s value until a submit button is clicked.
        The form's value is the value of the underlying element from the last submission.

        Examples:
            Convert any `UIElement` into a form:
                ```python
                prompt = mo.ui.text_area().form()
                ```

            Combine with `HTML.batch` to create a form made out of multiple `UIElements`:
                ```python
                form = (
                    mo.ui.md(
                        '''
                    **Enter your prompt.**

                    {prompt}

                    **Choose a random seed.**

                    {seed}
                    '''
                    )
                    .batch(
                        prompt=mo.ui.text_area(),
                        seed=mo.ui.number(),
                    )
                    .form()
                )
                ```

        Args:
            label: A text label for the form.
            bordered: Whether the form should have a border.
            loading: Whether the form should be in a loading state.
            submit_button_label: The label of the submit button.
            submit_button_tooltip: The tooltip of the submit button.
            submit_button_disabled: Whether the submit button should be disabled.
            clear_on_submit: Whether the form should clear its contents after submitting.
            show_clear_button: Whether the form should show a clear button.
            clear_button_label: The label of the clear button.
            clear_button_tooltip: The tooltip of the clear button.
            validate: A function that takes the form's value and returns an error message if invalid,
                or `None` if valid.
            on_change: Optional callback to run when this element's value changes. Defaults to None.
        """
        from marimo._plugins.ui._impl.input import form as form_plugin

        return form_plugin(
            element=self,
            label=label,
            bordered=bordered,
            loading=loading,
            submit_button_label=submit_button_label,
            submit_button_tooltip=submit_button_tooltip,
            submit_button_disabled=submit_button_disabled,
            clear_on_submit=clear_on_submit,
            show_clear_button=show_clear_button,
            clear_button_label=clear_button_label,
            clear_button_tooltip=clear_button_tooltip,
            validate=validate,
            on_change=on_change,
        )

    def send_message(
        self, message: dict[str, object], buffers: Optional[Sequence[bytes]]
    ) -> None:
        """
        Send a message to the element rendered on the frontend
        from the backend.
        """

        from marimo._messaging.ops import SendUIElementMessage

        SendUIElementMessage(
            ui_element=self._id,
            model_id=None,
            message=message,
            buffers=[
                base64.b64encode(buffer).decode() for buffer in (buffers or [])
            ],
        ).broadcast()

    def _update(self, value: S) -> None:
        """Update value, given a value from the frontend

        Calls the on_change handler with the element's new value as a
        side-effect.
        """
        self._value_frontend = value
        try:
            self._value = self._convert_value(value)
        except MarimoConvertValueException:
            raise

        if self._on_change is not None:
            self._on_change(self._value)

    def _on_update_completion(self) -> bool:
        """Callback to run after the kernel has processed a value update.

        Return true if the value of the component has changed, false otherwise
        """
        return False

    def __deepcopy__(self, memo: dict[int, Any]) -> UIElement[S, T]:
        # Custom deepcopy that excludes elements that can't be deepcopied
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if isinstance(v, RuntimeContext):
                setattr(result, k, v)
            else:
                setattr(result, k, copy.deepcopy(v, memo))

        # Get a new object ID and function namespace
        #
        # We use the new instance's functions, since they are typically bound
        # to the UI element instance. But we only use the new on_change
        # if the old one was bound to self.
        args: InitializationArgs[S, T]
        if (
            isinstance(self._args.on_change, types.MethodType)
            and self._args.on_change.__self__ is self
        ):
            # on_change was bound to self; use the new one.
            args = InitializationArgs(
                **{
                    # dataclass asdict does a deepcopy, we want shallow.
                    **{
                        field.name: getattr(self._args, field.name)
                        for field in fields(self._args)
                    },
                    "on_change": result._args.on_change,
                    "functions": result._args.functions,
                }
            )
        else:
            # otherwise, use the original on_change, which may be a state
            # SetFunctor or something else unrelated to this instance.
            args = InitializationArgs(
                **{
                    **{
                        field.name: getattr(self._args, field.name)
                        for field in fields(self._args)
                    },
                    "functions": result._args.functions,
                }
            )
        result._initialize(args)
        return result

    def _clone(self) -> UIElement[S, T]:
        """Clone a UIElement, returning one with a different id

        The clone will not synchronize with the original element.

        Composite UIElement may need to override this method to run
        their own side-effects.
        """
        return copy.deepcopy(self)

    def __bool__(self) -> bool:
        sys.stderr.write(
            "The truth value of a UIElement is always True. You "
            "probably want to call `.value` instead."
        )
        return True

    def _repr_markdown_(self) -> str:
        # When rendering to markdown, remove the marimo-ui-element tag
        # and render the inner-text escaped.
        return escape(self._inner_text)
