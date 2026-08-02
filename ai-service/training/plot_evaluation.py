import json
import matplotlib.pyplot as plt
import numpy as np

# Membaca hasil evaluasi
with open("evaluation_metrics.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# ==========================
# CONFUSION MATRIX
# ==========================

cm = np.array(data["confusion_matrix"]["matrix"])

fig, ax = plt.subplots(figsize=(5,5))

im = ax.imshow(cm)

ax.set_xticks([0,1])
ax.set_yticks([0,1])

ax.set_xticklabels(["Normal","Anomaly"])
ax.set_yticklabels(["Normal","Anomaly"])

ax.set_xlabel("Predicted Label")
ax.set_ylabel("True Label")
ax.set_title("Confusion Matrix")

for i in range(2):
    for j in range(2):
        ax.text(j, i, cm[i,j],
                ha="center",
                va="center",
                fontsize=14)

plt.tight_layout()
plt.savefig("confusion_matrix.png", dpi=300)
plt.close()

# ==========================
# ROC CURVE
# ==========================

fpr = data["roc"]["false_positive_rate"]
tpr = data["roc"]["true_positive_rate"]
auc = data["auc"]

plt.figure(figsize=(6,5))

plt.plot(fpr, tpr, linewidth=2,
         label=f"AUC = {auc:.3f}")

plt.plot([0,1],[0,1],"--")

plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("ROC Curve")
plt.legend(loc="lower right")

plt.tight_layout()
plt.savefig("roc_curve.png", dpi=300)
plt.close()

print("Selesai.")
print("confusion_matrix.png berhasil dibuat.")
print("roc_curve.png berhasil dibuat.")