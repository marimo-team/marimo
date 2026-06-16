# /// script
# dependencies = [
#     "marimo",
#     "flax>=0.10.0",
#     "jax>=0.4.0",
# ]
# requires-python = ">=3.11"
# ///

import marimo

__generated_with = "0.19.11"
app = marimo.App()

with app.setup:
    import jax.numpy as jnp
    from flax import nnx


@app.cell
def _():
    # Simple MLP. Stateless ops (relu) are plain functions in NNX, so they
    # don't appear in the tree -- only the Linear and Dropout modules do.
    mlp = nnx.Sequential(
        nnx.Linear(784, 256, rngs=nnx.Rngs(0)),
        nnx.relu,
        nnx.Dropout(0.2, rngs=nnx.Rngs(1)),
        nnx.Linear(256, 128, rngs=nnx.Rngs(2)),
        nnx.relu,
        nnx.Dropout(0.1, rngs=nnx.Rngs(3)),
        nnx.Linear(128, 10, rngs=nnx.Rngs(4)),
    )
    mlp
    return


@app.cell
def _():
    # CNN for image classification. Only trainable params are counted
    # (BatchNorm running statistics, like PyTorch buffers, are not).
    class SimpleCNN(nnx.Module):
        def __init__(self, rngs: nnx.Rngs):
            self.conv1 = nnx.Conv(3, 32, kernel_size=(3, 3), padding="SAME", rngs=rngs)
            self.bn1 = nnx.BatchNorm(32, rngs=rngs)
            self.conv2 = nnx.Conv(32, 64, kernel_size=(3, 3), padding="SAME", rngs=rngs)
            self.bn2 = nnx.BatchNorm(64, rngs=rngs)
            self.linear = nnx.Linear(64 * 8 * 8, 256, rngs=rngs)
            self.out = nnx.Linear(256, 10, rngs=rngs)

        def __call__(self, x):
            x = nnx.max_pool(nnx.relu(self.bn1(self.conv1(x))), (2, 2), strides=(2, 2))
            x = nnx.max_pool(nnx.relu(self.bn2(self.conv2(x))), (2, 2), strides=(2, 2))
            x = x.reshape(x.shape[0], -1)
            x = nnx.relu(self.linear(x))
            return self.out(x)

    cnn = SimpleCNN(nnx.Rngs(0))
    cnn
    return


@app.cell
def _():
    # Mini ResNet with skip connections
    class ResBlock(nnx.Module):
        def __init__(self, channels: int, rngs: nnx.Rngs):
            self.conv1 = nnx.Conv(channels, channels, kernel_size=(3, 3), padding="SAME", rngs=rngs)
            self.bn1 = nnx.BatchNorm(channels, rngs=rngs)
            self.conv2 = nnx.Conv(channels, channels, kernel_size=(3, 3), padding="SAME", rngs=rngs)
            self.bn2 = nnx.BatchNorm(channels, rngs=rngs)

        def __call__(self, x):
            residual = x
            out = nnx.relu(self.bn1(self.conv1(x)))
            out = self.bn2(self.conv2(out))
            return nnx.relu(out + residual)

    class MiniResNet(nnx.Module):
        def __init__(self, rngs: nnx.Rngs, num_classes: int = 10):
            self.stem = nnx.Conv(3, 64, kernel_size=(7, 7), strides=(2, 2), padding="SAME", rngs=rngs)
            self.stem_norm = nnx.BatchNorm(64, rngs=rngs)
            self.layer1 = nnx.Sequential(ResBlock(64, rngs), ResBlock(64, rngs))
            self.fc = nnx.Linear(64, num_classes, rngs=rngs)

        def __call__(self, x):
            x = nnx.relu(self.stem_norm(self.stem(x)))
            x = self.layer1(x)
            x = jnp.mean(x, axis=(1, 2))
            return self.fc(x)

    resnet = MiniResNet(nnx.Rngs(0))
    resnet
    return


@app.cell
def _():
    # Mini Transformer (MultiHeadAttention maps to the "weight" category)
    class TransformerBlock(nnx.Module):
        def __init__(self, d_model: int, nhead: int, rngs: nnx.Rngs):
            self.attn = nnx.MultiHeadAttention(
                num_heads=nhead, in_features=d_model, decode=False, rngs=rngs
            )
            self.norm1 = nnx.LayerNorm(d_model, rngs=rngs)
            self.ffn = nnx.Sequential(
                nnx.Linear(d_model, 512, rngs=rngs),
                nnx.relu,
                nnx.Linear(512, d_model, rngs=rngs),
            )
            self.norm2 = nnx.LayerNorm(d_model, rngs=rngs)

        def __call__(self, x):
            x = self.norm1(x + self.attn(x))
            return self.norm2(x + self.ffn(x))

    class MiniTransformer(nnx.Module):
        def __init__(
            self,
            rngs: nnx.Rngs,
            vocab_size: int = 10000,
            d_model: int = 256,
            nhead: int = 4,
            num_layers: int = 2,
            num_classes: int = 5,
        ):
            self.embedding = nnx.Embed(vocab_size, d_model, rngs=rngs)
            self.layers = nnx.Sequential(
                *[TransformerBlock(d_model, nhead, rngs) for _ in range(num_layers)]
            )
            self.classifier = nnx.Linear(d_model, num_classes, rngs=rngs)

        def __call__(self, x):
            x = self.embedding(x)
            x = self.layers(x)
            x = jnp.mean(x, axis=1)
            return self.classifier(x)

    transformer = MiniTransformer(nnx.Rngs(0))
    transformer
    return


@app.cell
def _():
    # NNX-specific layers: LoRA adapters (weight) and the parametric
    # PReLU activation (activation), plus a BatchNorm for the norm color.
    class Adapted(nnx.Module):
        def __init__(self, rngs: nnx.Rngs):
            self.lora = nnx.LoRALinear(128, 128, lora_rank=8, rngs=rngs)
            self.act = nnx.PReLU()
            self.norm = nnx.BatchNorm(128, rngs=rngs)
            self.head = nnx.Linear(128, 10, rngs=rngs)

        def __call__(self, x):
            return self.head(self.norm(self.act(self.lora(x))))

    Adapted(nnx.Rngs(0))
    return


if __name__ == "__main__":
    app.run()
