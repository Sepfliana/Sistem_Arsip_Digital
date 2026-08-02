"""Blueprint implementasi model Variational Autoencoder untuk audit log.

Modul ini hanya mendefinisikan arsitektur model. Training, threshold, dan
penyimpanan artefak model dilakukan oleh modul lain pada sprint berikutnya.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


MODEL_SPEC_PATH = Path(__file__).resolve().parents[1] / "model" / "model_spec.json"


ModelSpec = Dict[str, Any]


def get_keras_serialization_module() -> Any:
    """Mengambil modul serialisasi Keras lintas versi."""
    return getattr(keras, "saving", keras.utils)


def load_model_spec() -> ModelSpec:
    """Memuat konfigurasi arsitektur VAE dari model_spec.json."""
    with MODEL_SPEC_PATH.open("r", encoding="utf-8") as spec_file:
        return json.load(spec_file)


def validate_model_spec(model_spec: ModelSpec) -> None:
    """Memastikan konfigurasi model memenuhi kebutuhan Sprint 3."""
    input_features = model_spec.get("input_features", [])
    input_feature_count = model_spec.get("input_feature_count")
    latent_dimension = model_spec.get("latent_dimension")
    dropout = model_spec.get("dropout")

    if input_feature_count != 10 or len(input_features) != 10:
        raise ValueError("model_spec harus memiliki tepat 10 input feature.")

    if latent_dimension is None or int(latent_dimension) <= 0:
        raise ValueError("latent_dimension harus lebih besar dari 0.")

    if dropout is None or not 0 <= float(dropout) <= 1:
        raise ValueError("dropout harus berada di antara 0 sampai 1.")


@keras.utils.register_keras_serializable(package="sistem_arsip_digital")
class Sampling(layers.Layer):
    """Layer sampling latent vector dengan reparameterization trick."""

    def call(self, inputs: Tuple[tf.Tensor, tf.Tensor]) -> tf.Tensor:
        """Menghasilkan z dari latent mean dan latent log variance."""
        latent_mean, latent_log_variance = inputs
        batch_size = tf.shape(latent_mean)[0]
        latent_dimension = tf.shape(latent_mean)[1]
        epsilon = tf.random.normal(shape=(batch_size, latent_dimension))

        return latent_mean + tf.exp(0.5 * latent_log_variance) * epsilon


@keras.utils.register_keras_serializable(package="sistem_arsip_digital")
class VAE(keras.Model):
    """Subclass Keras Model untuk Variational Autoencoder audit log."""

    def __init__(self, encoder: keras.Model, decoder: keras.Model, **kwargs: Any) -> None:
        """Menyimpan encoder, decoder, dan tracker loss VAE."""
        super().__init__(**kwargs)
        self.encoder = encoder
        self.decoder = decoder
        self.total_loss_tracker = keras.metrics.Mean(name="total_loss")
        self.reconstruction_loss_tracker = keras.metrics.Mean(name="reconstruction_loss")
        self.kl_loss_tracker = keras.metrics.Mean(name="kl_loss")

    @property
    def metrics(self) -> list[keras.metrics.Metric]:
        """Mengembalikan daftar metric agar Keras dapat me-reset tiap epoch."""
        return [
            self.total_loss_tracker,
            self.reconstruction_loss_tracker,
            self.kl_loss_tracker,
        ]

    def call(self, inputs: tf.Tensor, training: bool = False) -> tf.Tensor:
        """Melakukan forward pass dari input ke rekonstruksi."""
        latent_mean, latent_log_variance, latent_vector = self.encoder(
            inputs,
            training=training,
        )
        _ = latent_mean, latent_log_variance
        return self.decoder(latent_vector, training=training)

    def calculate_losses(
        self,
        data: tf.Tensor,
        training: bool = True,
    ) -> Tuple[tf.Tensor, tf.Tensor, tf.Tensor]:
        """Menghitung reconstruction loss, KL divergence, dan total loss."""
        latent_mean, latent_log_variance, latent_vector = self.encoder(data, training=training)
        reconstruction = self.decoder(latent_vector, training=training)

        reconstruction_loss = tf.reduce_mean(
            tf.reduce_mean(tf.square(data - reconstruction), axis=1)
        )
        kl_loss = -0.5 * tf.reduce_mean(
            tf.reduce_sum(
                1 + latent_log_variance - tf.square(latent_mean) - tf.exp(latent_log_variance),
                axis=1,
            )
        )
        total_loss = reconstruction_loss + kl_loss

        return total_loss, reconstruction_loss, kl_loss

    def train_step(self, data: tf.Tensor) -> Dict[str, tf.Tensor]:
        """Menjalankan satu langkah training VAE tanpa loop training manual."""
        if isinstance(data, tuple):
            data = data[0]

        with tf.GradientTape() as tape:
            total_loss, reconstruction_loss, kl_loss = self.calculate_losses(data, training=True)

        gradients = tape.gradient(total_loss, self.trainable_weights)
        self.optimizer.apply_gradients(zip(gradients, self.trainable_weights))
        self.total_loss_tracker.update_state(total_loss)
        self.reconstruction_loss_tracker.update_state(reconstruction_loss)
        self.kl_loss_tracker.update_state(kl_loss)

        return {
            "loss": self.total_loss_tracker.result(),
            "reconstruction_loss": self.reconstruction_loss_tracker.result(),
            "kl_loss": self.kl_loss_tracker.result(),
        }

    def test_step(self, data: tf.Tensor) -> Dict[str, tf.Tensor]:
        """Menjalankan satu langkah evaluasi VAE."""
        if isinstance(data, tuple):
            data = data[0]

        total_loss, reconstruction_loss, kl_loss = self.calculate_losses(data, training=False)
        self.total_loss_tracker.update_state(total_loss)
        self.reconstruction_loss_tracker.update_state(reconstruction_loss)
        self.kl_loss_tracker.update_state(kl_loss)

        return {
            "loss": self.total_loss_tracker.result(),
            "reconstruction_loss": self.reconstruction_loss_tracker.result(),
            "kl_loss": self.kl_loss_tracker.result(),
        }

    def get_config(self) -> Dict[str, Any]:
        """Mengembalikan konfigurasi agar model dapat dimuat ulang."""
        serialization = get_keras_serialization_module()
        config = super().get_config()
        config.update(
            {
                "encoder": serialization.serialize_keras_object(self.encoder),
                "decoder": serialization.serialize_keras_object(self.decoder),
            }
        )
        return config

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "VAE":
        """Membangun ulang VAE dari konfigurasi Keras."""
        serialization = get_keras_serialization_module()
        encoder_config = config.pop("encoder")
        decoder_config = config.pop("decoder")
        encoder = serialization.deserialize_keras_object(
            encoder_config,
            custom_objects=get_custom_objects(),
        )
        decoder = serialization.deserialize_keras_object(
            decoder_config,
            custom_objects=get_custom_objects(),
        )
        return cls(encoder=encoder, decoder=decoder, **config)


def build_encoder(model_spec: ModelSpec) -> keras.Model:
    """Membangun encoder VAE berdasarkan model_spec.json."""
    input_dimension = int(model_spec["input_feature_count"])
    latent_dimension = int(model_spec["latent_dimension"])
    encoder_layers = model_spec["hidden_layers"]["encoder"]
    activation = str(model_spec["activation"])
    dropout = float(model_spec["dropout"])
    use_batch_normalization = bool(model_spec["batch_normalization"])

    encoder_inputs = keras.Input(shape=(input_dimension,), name="encoder_input")
    x = encoder_inputs

    for index, units in enumerate(encoder_layers):
        x = layers.Dense(int(units), name=f"encoder_dense_{index + 1}")(x)
        if use_batch_normalization:
            x = layers.BatchNormalization(name=f"encoder_batch_norm_{index + 1}")(x)
        x = layers.Activation(activation, name=f"encoder_{activation}_{index + 1}")(x)
        if index == 0:
            x = layers.Dropout(dropout, name="encoder_dropout")(x)

    latent_mean = layers.Dense(latent_dimension, name="latent_mean")(x)
    latent_log_variance = layers.Dense(latent_dimension, name="latent_log_variance")(x)
    latent_vector = Sampling(name="sampling")([latent_mean, latent_log_variance])

    return keras.Model(
        encoder_inputs,
        [latent_mean, latent_log_variance, latent_vector],
        name="audit_log_encoder",
    )


def build_decoder(model_spec: ModelSpec) -> keras.Model:
    """Membangun decoder VAE berdasarkan model_spec.json."""
    input_dimension = int(model_spec["input_feature_count"])
    latent_dimension = int(model_spec["latent_dimension"])
    decoder_layers = model_spec["hidden_layers"]["decoder"]
    activation = str(model_spec["activation"])
    dropout = float(model_spec["dropout"])
    use_batch_normalization = bool(model_spec["batch_normalization"])
    output_activation = str(model_spec["output_activation"])

    decoder_inputs = keras.Input(shape=(latent_dimension,), name="decoder_input")
    x = decoder_inputs

    for index, units in enumerate(decoder_layers):
        x = layers.Dense(int(units), name=f"decoder_dense_{index + 1}")(x)
        if use_batch_normalization:
            x = layers.BatchNormalization(name=f"decoder_batch_norm_{index + 1}")(x)
        x = layers.Activation(activation, name=f"decoder_{activation}_{index + 1}")(x)
        if index == 0:
            x = layers.Dropout(dropout, name="decoder_dropout")(x)

    decoder_outputs = layers.Dense(
        input_dimension,
        activation=output_activation,
        name="decoder_output",
    )(x)

    return keras.Model(decoder_inputs, decoder_outputs, name="audit_log_decoder")


def build_optimizer(model_spec: ModelSpec) -> keras.optimizers.Optimizer:
    """Membangun optimizer berdasarkan konfigurasi model_spec.json."""
    optimizer = keras.optimizers.get(str(model_spec["optimizer"]))
    optimizer.learning_rate = float(model_spec["learning_rate"])

    return optimizer


def build_vae() -> Tuple[keras.Model, keras.Model, VAE]:
    """Membangun encoder, decoder, dan VAE model dari model_spec.json."""
    model_spec = load_model_spec()
    validate_model_spec(model_spec)

    encoder = build_encoder(model_spec)
    decoder = build_decoder(model_spec)
    vae_model = VAE(encoder, decoder, name="audit_log_vae")
    vae_model.compile(optimizer=build_optimizer(model_spec))

    return encoder, decoder, vae_model


def get_custom_objects() -> Dict[str, object]:
    """Mengembalikan custom object untuk keras.models.load_model()."""
    return {
        "Sampling": Sampling,
        "VAE": VAE,
    }


if __name__ == "__main__":
    model_spec = load_model_spec()
    encoder_model, decoder_model, vae = build_vae()
    encoder_model.summary()
    decoder_model.summary()

    dummy_input = tf.zeros((1, model_spec["input_feature_count"]), dtype=tf.float32)
    dummy_output = vae(dummy_input, training=False)
    if tuple(dummy_output.shape) != (1, model_spec["input_feature_count"]):
        raise RuntimeError("Forward pass VAE tidak menghasilkan output berdimensi 10.")

    vae.build((None, model_spec["input_feature_count"]))
    vae.summary()

    custom_objects = get_custom_objects()
    if "Sampling" not in custom_objects or "VAE" not in custom_objects:
        raise RuntimeError("Custom objects harus memiliki key Sampling dan VAE.")

    print("Forward pass berhasil tanpa menjalankan training.")
    print("Custom objects berisi Sampling dan VAE.")
    print("VAE compile berhasil tanpa menjalankan training.")
