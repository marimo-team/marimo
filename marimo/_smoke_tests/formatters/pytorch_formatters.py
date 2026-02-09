# /// script
# dependencies = [
#     "marimo",
#     "torch==2.10.0",
# ]
# requires-python = ">=3.13"
# ///

import marimo

__generated_with = "0.19.11"
app = marimo.App()

with app.setup:
    import torch.nn as nn


@app.cell
def _():
    # Simple MLP
    mlp = nn.Sequential(
        nn.Linear(784, 256),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(256, 128),
        nn.ReLU(),
        nn.Dropout(0.1),
        nn.Linear(128, 10),
    )
    mlp
    return


@app.cell
def _():
    # CNN for image classification
    class SimpleCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 32, kernel_size=3, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(),
                nn.MaxPool2d(2),
                nn.Conv2d(32, 64, kernel_size=3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(),
                nn.MaxPool2d(2),
            )
            self.classifier = nn.Sequential(
                nn.Linear(64 * 8 * 8, 256),
                nn.ReLU(),
                nn.Dropout(0.5),
                nn.Linear(256, 10),
            )

        def forward(self, x):
            x = self.features(x)
            x = x.view(x.size(0), -1)
            x = self.classifier(x)
            return x

    cnn = SimpleCNN()
    cnn
    return


@app.cell
def _():
    import torch

    # Mini ResNet with skip connections
    class ResBlock(nn.Module):
        def __init__(self, channels):
            super().__init__()
            self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
            self.bn1 = nn.BatchNorm2d(channels)
            self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
            self.bn2 = nn.BatchNorm2d(channels)
            self.relu = nn.ReLU()

        def forward(self, x):
            residual = x
            out = self.relu(self.bn1(self.conv1(x)))
            out = self.bn2(self.conv2(out))
            out = out + residual
            return self.relu(out)

    class MiniResNet(nn.Module):
        def __init__(self, num_classes=10):
            super().__init__()
            self.stem = nn.Sequential(
                nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3),
                nn.BatchNorm2d(64),
                nn.ReLU(),
                nn.MaxPool2d(3, stride=2, padding=1),
            )
            self.layer1 = nn.Sequential(ResBlock(64), ResBlock(64))
            self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
            self.fc = nn.Linear(64, num_classes)

        def forward(self, x):
            x = self.stem(x)
            x = self.layer1(x)
            x = self.avgpool(x)
            x = torch.flatten(x, 1)
            x = self.fc(x)
            return x

    resnet = MiniResNet()
    resnet
    return


@app.cell
def _():
    # Mini Transformer
    class MiniTransformer(nn.Module):
        def __init__(
            self,
            vocab_size=10000,
            d_model=256,
            nhead=4,
            num_layers=2,
            num_classes=5,
        ):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, d_model)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=512,
                batch_first=True,
            )
            self.transformer = nn.TransformerEncoder(
                encoder_layer, num_layers=num_layers
            )
            self.classifier = nn.Linear(d_model, num_classes)

        def forward(self, x):
            x = self.embedding(x)
            x = self.transformer(x)
            x = x.mean(dim=1)
            x = self.classifier(x)
            return x

    transformer = MiniTransformer()
    transformer
    return


@app.cell
def _():
    # Layers with many kwargs to test long extra_repr
    verbose = nn.Sequential(
        nn.Conv2d(
            3,
            64,
            kernel_size=7,
            stride=2,
            padding=3,
            dilation=1,
            groups=1,
            bias=False,
            padding_mode="zeros",
        ),
        nn.BatchNorm2d(
            64, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True
        ),
        nn.LSTM(
            input_size=256,
            hidden_size=512,
            num_layers=3,
            batch_first=True,
            dropout=0.3,
            bidirectional=True,
        ),
        nn.TransformerEncoderLayer(
            d_model=512,
            nhead=8,
            dim_feedforward=2048,
            dropout=0.1,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        ),
    )
    verbose
    return


@app.cell
def _():
    # Fully frozen model (e.g. pretrained feature extractor)
    frozen_mlp = nn.Sequential(
        nn.Linear(784, 256),
        nn.ReLU(),
        nn.Linear(256, 10),
    )
    for p in frozen_mlp.parameters():
        p.requires_grad = False

    frozen_mlp
    return


@app.cell
def _():
    # Partially frozen: freeze backbone, train classifier head
    class FineTuned(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = nn.Sequential(
                nn.Conv2d(3, 64, kernel_size=3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(),
                nn.Conv2d(64, 128, kernel_size=3, padding=1),
                nn.BatchNorm2d(128),
                nn.ReLU(),
            )
            self.head = nn.Sequential(
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, 10),
            )
            # Freeze backbone
            for p in self.backbone.parameters():
                p.requires_grad = False

        def forward(self, x):
            x = self.backbone(x)
            x = x.mean(dim=[2, 3])
            x = self.head(x)
            return x

    FineTuned()
    return


if __name__ == "__main__":
    app.run()
