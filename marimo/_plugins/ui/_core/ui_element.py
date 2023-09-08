# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import abc
import copy
import uuid
from typing import TYPE_CHECKING, Callable, Generic, Optional, TypeVar, cast

from marimo import _loggers
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType, build_ui_plugin
from marimo._plugins.ui._core import ids
from marimo._runtime.context import get_context

if TYPE_CHECKING:
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


class MarimoConvertValueException(Exception):
    pass


@mddoc
class UIElement(Html, Generic[S, T], metaclass=abc.ABCMeta):
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

    _value: T

    def __init__(
        self,
        component_name: str,
        initial_value: S,
        label: Optional[str],
        on_change: Optional[Callable[[T], None]],
        args: dict[str, JSONType],
        slotted_html: str = "",
    ) -> None:
        """Initialize a UIElement

        Args:
        ----
        component_name: tag name of the custom element
        initial_value: initial value of the element in the frontend
        label: markdown string, label of element
        args: arguments that the element takes
        slotted_html: any html to slot in the custom element
        on_change: callback, called with element's new value on change
        """
        # arguments stored in signature order for cloning
        self._args = (
            component_name,
            initial_value,
            label,
            on_change,
            args,
            slotted_html,
        )
        self._initialized = False
        self._initialize(*self._args)
        self._initialized = True

    def _initialize(
        self,
        component_name: str,
        initial_value: S,
        label: Optional[str],
        on_change: Optional[Callable[[T], None]],
        args: dict[str, JSONType],
        slotted_html: str,
    ) -> None:
        """Initialize the UIElement

        Split out from __init__ so _clone() typechecks
        """
        # Random token
        #
        # Every element is annotated with a random token, which by design is
        # different every time the element is constructed (i.e., every time a
        # cell runs): this guarantees that re-running a cell that creates a UI
        # element will trigger a re-render and reset it to its initial value.
        # We need this to ensure that the element on the page is synchronized
        # with the element in the kernel.
        self._random_id = str(uuid.uuid4())

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
            self._id = get_context().take_id()
        except ids.NoIDProviderException:
            self._id = self._random_id

        ctx = get_context()
        if ctx.initialized:
            ctx.ui_element_registry.register(self._id, self)

        # an Instantiate request may want us to override the initial value
        if ctx.initialized:
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
                    S, ctx.kernel.get_ui_initial_value(self._id)
                )
            except KeyError:
                # we weren't asked to override the UI element's value
                pass
        self._initial_value_frontend = initial_value
        self._value = self._initial_value = self._convert_value(initial_value)
        self._on_change = on_change

        self._inner_text = build_ui_plugin(
            component_name,
            initial_value,
            label,
            args,
            slotted_html,
        )
        self._text = (
            f"<marimo-ui-element object-id='{self._id}' "
            + f"random-id='{self._random_id}'>"
            + self._inner_text
            + "</marimo-ui-element>"
        )

    @abc.abstractmethod
    def _convert_value(self, value: S) -> T:
        """Converts a value from the frontend to a value for the `UIElement`

        This method must convert `value`, the JSON-decoded value sent by the
        frontend, to a value of type `T` for the `UIElement`.
        """
        pass

    @property
    def value(self) -> T:
        """The element's current value."""
        ctx = get_context()
        if (
            ctx.initialized
            and ctx.kernel.execution_context is not None
            and not ctx.kernel.execution_context.setting_element_value
            and (
                ctx.kernel.execution_context.cell_id
                == ctx.ui_element_registry.get_cell(self._id)
            )
        ):
            raise RuntimeError(
                "Accessing the value of a UIElement in the cell that created "
                "it is not allowed. Fix: move the value access to another "
                "cell."
            )
        return self._value

    @mddoc
    def form(self, label: str = "") -> form_plugin[S, T]:
        """Create a submittable form out of this `UIElement`.

        Use this method to create a form that gates the submission
        of a `UIElement`s value until a submit button is clicked.

        The value of the `form` is the value of the underlying
        element the last time the form was submitted.

        **Examples.**

        Convert any `UIElement` into a form:

        ```python
        prompt = mo.ui.text_area().form()
        ```

        Combine with `HTML.batch` to create a form made out of multiple
        `UIElements`:

        ```python
        form = mo.ui.md(
            '''
            **Enter your prompt.**

            {prompt}

            **Choose a random seed.**

            {seed}
            '''
        ).batch(
            prompt=mo.ui.text_area(),
            seed=mo.ui.number(),
        ).form()
        ```

        **Args.**

        - `label`: A text label for the form.
        """
        from marimo._plugins.ui._impl.input import form as form_plugin

        return form_plugin(element=self, label=label)

    def _update(self, value: S) -> None:
        """Update value, given a value from the frontend

        Calls the on_change handler with the element's new value as a
        side-effect.
        """
        try:
            self._value = self._convert_value(value)
        except MarimoConvertValueException:
            raise

        if self._on_change is not None:
            self._on_change(self._value)

    def __del__(self) -> None:
        ctx = get_context()
        if ctx.initialized:
            ctx.ui_element_registry.delete(self._id, id(self))

    def _clone(self) -> UIElement[S, T]:
        """Clone a UIElement, returning one with a different id

        The clone will not synchronize with the original element.

        Composite UIElement may need to override this method to run
        their own side-effects.
        """
        duplicate = copy.deepcopy(self)
        duplicate._initialize(*self._args)
        return duplicate
