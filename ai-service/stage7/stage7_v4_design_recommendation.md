# V4 Design Recommendation

Do not use a single-feature tail. Select only raw-domain compound scenarios whose exact `(hour bucket, activity, device, IP category)` is unseen or empirically low-frequency in normal data, while the `(activity, object bucket, duration bucket)` remains operationally plausible. V4 requires a predeclared rarity threshold and a per-scenario Localhost FPR gate before implementation.

Decision: **V4 DESIGN READY**.
