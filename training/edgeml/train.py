"""Train the float32 baseline.

python -m edgeml.train --data data/processed/dataset.npz --out models
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import dataset as ds


def to_float(x: np.ndarray) -> np.ndarray:
    """uint8 (N, H, W) -> float32 (N, H, W, 1) in [0, 1], the model's input convention."""
    return (x.astype(np.float32) / 255.0)[..., np.newaxis]


def _augmenter(seed: int):
    import keras
    from keras import layers

    # Mild, camera-plausible changes: mirror, small shift, exposure.
    return keras.Sequential(
        [
            layers.RandomFlip("horizontal", seed=seed),
            layers.RandomTranslation(0.08, 0.08, fill_mode="nearest", seed=seed),
            layers.RandomBrightness(0.15, value_range=(0.0, 1.0), seed=seed),
            layers.RandomContrast(0.2, value_range=(0.0, 1.0), seed=seed),
        ],
        name="augment",
    )


def train(
    data_path: Path,
    out: Path,
    *,
    epochs: int = 40,
    batch_size: int = 32,
    learning_rate: float = 2e-3,
    width: float = 1.0,
    seed: int = 0,
) -> dict:
    import keras
    import tensorflow as tf

    from .model import build_model

    keras.utils.set_random_seed(seed)

    data = ds.load(data_path)
    labels = [str(label) for label in data["labels"]]
    x_train, y_train = to_float(data["x_train"]), data["y_train"]
    x_val, y_val = to_float(data["x_val"]), data["y_val"]
    if len(x_train) == 0:
        raise SystemExit("the training split is empty")

    # Weight classes inversely to their frequency so a rare class is not ignored.
    counts = np.bincount(y_train, minlength=len(labels)).astype(np.float64)
    class_weight = {i: float(len(y_train) / (len(labels) * n)) if n > 0 else 0.0 for i, n in enumerate(counts)}

    augment = _augmenter(seed)
    train_ds = (
        tf.data.Dataset.from_tensor_slices((x_train, y_train))
        .shuffle(len(x_train), seed=seed)
        .batch(batch_size)
        .map(lambda x, y: (tf.clip_by_value(augment(x, training=True), 0.0, 1.0), y))
        .prefetch(tf.data.AUTOTUNE)
    )
    has_val = len(x_val) > 0
    val_ds = tf.data.Dataset.from_tensor_slices((x_val, y_val)).batch(batch_size) if has_val else None

    model = build_model(num_classes=len(labels), width=width)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=["accuracy"],
    )

    callbacks = []
    if has_val:
        callbacks.append(
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=10, start_from_epoch=10, restore_best_weights=True
            )
        )
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=2,
    )

    out.mkdir(parents=True, exist_ok=True)
    model.save(out / "float.keras")

    metrics = {
        "epochs_run": len(history.history["loss"]),
        "params": int(model.count_params()),
        "train_accuracy": float(history.history["accuracy"][-1]),
        "val_accuracy": float(max(history.history["val_accuracy"])) if has_val else None,
        "train_samples": int(len(x_train)),
        "val_samples": int(len(x_val)),
    }
    (out / "train_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path("data/processed/dataset.npz"))
    parser.add_argument("--out", type=Path, default=Path("models"))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-3)
    parser.add_argument("--width", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    metrics = train(
        args.data,
        args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        width=args.width,
        seed=args.seed,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
