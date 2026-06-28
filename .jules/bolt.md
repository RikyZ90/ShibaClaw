## 2024-06-28 - Avoid multiple iterations and temporary lists for counting
**Learning:** In Python, creating intermediate lists using list comprehensions just to call `len()` is inefficient, especially when iterating over the same underlying collection multiple times (like in `status()` methods). It wastes memory and CPU.
**Action:** Consolidate multiple counts into a single loop using integer accumulators to make operations O(N) instead of O(k*N), and avoid unnecessary list allocations.
