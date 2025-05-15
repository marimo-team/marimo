import marimo

__generated_with = "0.13.7"
app = marimo.App(width="medium")


@app.cell
def __1():
    import time
    from transformers.utils.notebook import NotebookProgressCallback
    from transformers.training_args import IntervalStrategy
    return IntervalStrategy, NotebookProgressCallback, time


@app.cell
def _(
    MockTrainingArgs,
    MockTrainingControl,
    MockTrainingState,
    NotebookProgressCallback,
    time,
):
    def simulate_transformers_training():
        # Training parameters
        num_train_epochs = 5
        steps_per_epoch = 100
        total_steps = num_train_epochs * steps_per_epoch

        # Initialize state, args, and control
        state = MockTrainingState(total_steps, num_train_epochs)
        args = MockTrainingArgs()
        control = MockTrainingControl()

        # Initialize the callback
        callback = NotebookProgressCallback()

        # Start training
        callback.on_train_begin(args, state, control)

        # Simulate epochs
        for epoch in range(1, num_train_epochs + 1):
            state.epoch = epoch

            # Simulate steps within epoch
            for step in range(1, steps_per_epoch + 1):
                state.global_step = (epoch - 1) * steps_per_epoch + step

                # Simulate work
                time.sleep(0.01)  # Reduced sleep time for faster simulation

                # Update progress
                callback.on_step_end(args, state, control)

            # Call on_evaluate
            callback.on_evaluate(args, state, control, metrics={})

        # End training
        callback.on_train_end(args, state, control)


    simulate_transformers_training()
    return


@app.cell
def _(IntervalStrategy):
    # Create a mock training state and args for the callback
    class MockTrainingState:
        def __init__(self, max_steps, num_train_epochs):
            self.max_steps = max_steps
            self.num_train_epochs = num_train_epochs
            self.global_step = 0
            self.epoch = 0
            self.log_history = []


    class MockTrainingArgs:
        def __init__(self):
            self.eval_strategy = IntervalStrategy.EPOCH


    class MockTrainingControl:
        def __init__(self):
            pass
    return MockTrainingArgs, MockTrainingControl, MockTrainingState


if __name__ == "__main__":
    app.run()
