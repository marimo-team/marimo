import marimo

__generated_with = "0.2.10"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        ###  Micrograd demo
        """
    )
    return


@app.cell
def __():
    import random
    import numpy as np
    import matplotlib.pyplot as plt
    return np, plt, random


@app.cell
def __():
    from micrograd.engine import Value
    from micrograd.nn import Neuron, Layer, MLP
    return Layer, MLP, Neuron, Value


@app.cell
def __(np, random):
    np.random.seed(1337)
    random.seed(1337)
    return


@app.cell
def __(plt):
    # make up a dataset

    from sklearn.datasets import make_moons, make_blobs

    X, y = make_moons(n_samples=100, noise=0.1)

    y = y * 2 - 1  # make y be -1 or 1
    # visualize in 2D
    plt.figure(figsize=(5, 5))
    plt.scatter(X[:, 0], X[:, 1], c=y, s=20, cmap="jet")
    return X, make_blobs, make_moons, y


@app.cell
def __(MLP):
    # initialize a model
    model = MLP(2, [16, 16, 1])  # 2-layer neural network
    print(model)
    print("number of parameters", len(model.parameters()))
    return model,


@app.cell
def __(Value, X, model, np, y):
    # loss function
    def loss(batch_size=None):

        # inline DataLoader :)
        if batch_size is None:
            Xb, yb = X, y
        else:
            ri = np.random.permutation(X.shape[0])[:batch_size]
            Xb, yb = X[ri], y[ri]
        inputs = [list(map(Value, xrow)) for xrow in Xb]

        # forward the model to get scores
        scores = list(map(model, inputs))

        # svm "max-margin" loss
        losses = [(1 + -yi * scorei).relu() for yi, scorei in zip(yb, scores)]
        data_loss = sum(losses) * (1.0 / len(losses))
        # L2 regularization
        alpha = 1e-4
        reg_loss = alpha * sum((p * p for p in model.parameters()))
        total_loss = data_loss + reg_loss

        # also get accuracy
        accuracy = [
            (yi > 0) == (scorei.data > 0) for yi, scorei in zip(yb, scores)
        ]
        return total_loss, sum(accuracy) / len(accuracy)

    _total_loss, _acc = loss()
    print(_total_loss, _acc)
    return loss,


@app.cell
def __(loss, model):
    # optimization
    for k in range(20):

        # forward
        total_loss, acc = loss()

        # backward
        model.zero_grad()
        total_loss.backward()

        # update (sgd)
        learning_rate = 1.0 - 0.9 * k / 100
        for p in model.parameters():
            p.data -= learning_rate * p.grad

        if k % 1 == 0:
            print(f"step {k} loss {total_loss.data}, accuracy {acc*100}%")
    return acc, k, learning_rate, p, total_loss


@app.cell
def __(Value, X, model, np, plt, y):
    # visualize decision boundary

    h = 0.25
    x_min, x_max = X[:, 0].min() - 1, X[:, 0].max() + 1
    y_min, y_max = X[:, 1].min() - 1, X[:, 1].max() + 1
    xx, yy = np.meshgrid(
        np.arange(x_min, x_max, h), np.arange(y_min, y_max, h)
    )
    Xmesh = np.c_[xx.ravel(), yy.ravel()]
    inputs = [list(map(Value, xrow)) for xrow in Xmesh]
    scores = list(map(model, inputs))
    Z = np.array([s.data > 0 for s in scores])
    Z = Z.reshape(xx.shape)

    fig = plt.figure()
    plt.contourf(xx, yy, Z, cmap=plt.cm.Spectral, alpha=0.8)
    plt.scatter(X[:, 0], X[:, 1], c=y, s=40, cmap=plt.cm.Spectral)
    plt.xlim(xx.min(), xx.max())
    plt.ylim(yy.min(), yy.max())
    plt.gca()
    return (
        Xmesh,
        Z,
        fig,
        h,
        inputs,
        scores,
        x_max,
        x_min,
        xx,
        y_max,
        y_min,
        yy,
    )


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
