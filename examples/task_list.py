import marimo

__generated_with = "0.1.4"
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
    get_tasks, set_tasks = mo.state([])
    mutation_signal, set_mutation_signal = mo.state(False)
    return get_tasks, mutation_signal, set_mutation_signal, set_tasks


@app.cell
def __(mo, mutation_signal):
    mutation_signal

    task_entry_box = mo.ui.text(placeholder="a task ...")
    return task_entry_box,


@app.cell
def __(Task, mo, set_mutation_signal, set_tasks, task_entry_box):
    def add_task():
        if task_entry_box.value:
            set_tasks(lambda v: v + [Task(task_entry_box.value)])
        set_mutation_signal(True)


    add_task_button = mo.ui.button(
        label="add task",
        on_change=lambda _: add_task(),
    )

    clear_tasks_button = mo.ui.button(
        label="clear completed tasks",
        on_change=lambda _: set_tasks(
            lambda v: [task for task in v if not task.done]
        ),
    )
    return add_task, add_task_button, clear_tasks_button


@app.cell
def __(add_task_button, clear_tasks_button, mo, task_entry_box):
    mo.hstack(
        [task_entry_box, add_task_button, clear_tasks_button], justify="start"
    )
    return


@app.cell
def __(Task, get_tasks, mo, set_tasks):
    task_list = mo.ui.array(
        [mo.ui.checkbox(value=task.done, label=task.name) for task in get_tasks()],
        label="tasks",
        on_change=lambda v: set_tasks(
            [Task(task.name, done=v[i]) for i, task in enumerate(get_tasks())]
        ),
    )
    return task_list,


@app.cell
def __(mo, task_list):
    mo.as_html(task_list) if task_list.value else mo.md("No tasks! 🎉")
    return


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
