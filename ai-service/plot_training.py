import json
import matplotlib.pyplot as plt

# Membaca history training
with open("training/history.json", "r", encoding="utf-8") as f:
    history = json.load(f)

loss = history["loss"]
val_loss = history["val_loss"]

epochs = range(1, len(loss) + 1)

plt.figure(figsize=(8,5))

plt.plot(epochs, loss, label="Training Loss", linewidth=2)
plt.plot(epochs, val_loss, label="Validation Loss", linewidth=2)

plt.title("Training Loss dan Validation Loss Model VAE")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.grid(True)
plt.legend()

plt.tight_layout()

plt.savefig("training/training_loss.png", dpi=300)

plt.show()