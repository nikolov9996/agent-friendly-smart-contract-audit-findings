---
id: 25751
severity: "Medium"
---

# Strategy::checkPoolActivity() does not look as far back as it should

## Description



## Proof of Concept

The way the observations work is:

1. The current tick of the pool is taken.
2. The tick cumulative of the most recent observation is taken.
3. The tick cumulative of the second most recent observation is taken.
4. These cumulative ticks are subtracted and divided by the delta timestamp, leading to the tick at the **most recent observation**.
5. The current tick of the pool is compared with the tick of the most recent observation in the first iteration. In the second, it's the most recent tick with the second most recent, so on and so forth.

However, when checking `lookAgo` vs `timestamp`, it is using the timestamp of the second most recent observation, but it evaluated the tick of the most recent observation. Thus, it will return 1 tick too early.

Note: recent and second most recent can be shifted in time to 3rd and 4th and so on.

## Recommendation

The timestamp check should be made on the `nextTimestamp`, before it is updated to `timestamp` in the loop.
