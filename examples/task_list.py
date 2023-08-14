import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Task List")
    return


@app.cell
def __(add_task_button, clear_tasks_button, mo, state, task):
    # Construct the task list based on the task list state.
    #
    # This cell will re-run and reconstruct the task list with updated state 
    # whenever either of the buttons are clicked, since they include references 
    # to the button elements.
    task_list = mo.ui.array(
        [
            mo.ui.checkbox(value=v, label=l)
            for v, l in zip(state.values, state.labels)
        ],
        label="tasks",
    )

    (
        task,
        add_task_button,
        clear_tasks_button,
        task_list if state.values else mo.md("No tasks! 🎉"),
    )
    return task_list,


@app.cell
def __(state, task_list):
    # This cell runs whenever a task is checked or unchecked, updating the state.
    #
    # This makes use of the fact that writing to attributes (non-globals) doesn't
    # trigger reactive execution.
    #
    # In the future we may introduce an API for setting state.
    state.values[:] = task_list.value
    return


@app.cell
def __(mo):
    # A text input for entering a task
    task = mo.ui.text(placeholder="a task ...")

    class TaskListState:
        """
        This class holds the state of the task list: the tasks (labels),
        and whether they've been completed (values).
        """
        def __init__(self):
            # The task labels
            self.labels = []
            # Whether each label is checked
            self.values = []

        def add_task(self):
            if task.value:
                # Add the current value of the task input to `self.labels`
                self.labels.append(task.value)
                # The task starts as incomplete
                self.values.append(False)
            return self

        def clear_tasks(self):
            # Remove all completed tasks from state
            self.labels[:] = [
                label
                for i, label in enumerate(self.labels)
                if not self.values[i]
            ]
            self.values[:] = [v for v in self.values if not v]
            return self

    state = TaskListState()

    # Buttons to add and remove tasks; these buttons mutate state when they
    # are clicked.
    add_task_button = mo.ui.button(
        value=state,
        on_click=lambda state: state.add_task(),
        label="add task",
    )

    clear_tasks_button = mo.ui.button(
        value=state,
        on_click=lambda state: state.clear_tasks(),
        label="clear completed tasks",
    )
    return TaskListState, add_task_button, clear_tasks_button, state, task


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
