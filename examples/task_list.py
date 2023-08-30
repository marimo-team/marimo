import marimo

__generated_with = "0.1.2"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Task List").left()
    return


@app.cell
def __(dataclass):
    @dataclass
    class Task:
        name: str
        done: bool = False
    return Task,


@app.cell
def __(mo):
    tasks, set_tasks = mo.state([])
    return set_tasks, tasks


@app.cell
def __(Task, mo, set_tasks, tasks):
    task_entry_box = mo.ui.text(placeholder="a task ...")

    add_task_button = mo.ui.button(
        label="add task",
        on_change=lambda _: set_tasks(tasks.value + [Task(task_entry_box.value)]),
    )

    clear_tasks_button = mo.ui.button(
        label="clear completed tasks",
        on_change=lambda _: set_tasks(
            [task for task in tasks.value if not task.done]
        ),
    )
    return add_task_button, clear_tasks_button, task_entry_box


@app.cell
def __(add_task_button, clear_tasks_button, mo, task_entry_box):
    mo.hstack(
        [task_entry_box, add_task_button, clear_tasks_button], justify="start"
    )
    return


@app.cell
def __(mo, task_list):
    mo.as_html(task_list)
    return


@app.cell
def __(Task, mo, set_tasks, tasks):
    task_list = mo.ui.array(
        [mo.ui.checkbox(value=task.done, label=task.name) for task in tasks.value],
        label="tasks",
        on_change=lambda v: set_tasks(
            [Task(task.name, done=v[i]) for i, task in enumerate(tasks.value)]
        ),
    )
    return task_list,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    from dataclasses import dataclass
    return dataclass,


if __name__ == "__main__":
    app.run()
