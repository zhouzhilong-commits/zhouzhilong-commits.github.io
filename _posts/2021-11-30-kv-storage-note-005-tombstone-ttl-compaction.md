---
layout: single
title: "KV存储笔记：删除、tombstone、TTL 与压缩（避免“删了又回来”）"
series: kv_storage
categories: [storage]
tags: [存储, kv存储, 删除, tombstone, TTL, compaction]
date: 2021-11-30
permalink: /kv-storage-note-005-tombstone-ttl-compaction/
---

在 KV 存储里，“删除”很少是一个真正的 delete。尤其当底层是 LSM：

- 数据不可就地删除
- 多副本系统里，删除必须传播并最终收敛
- compaction 负责真正回收空间

这一篇把三个容易线上踩坑的点放在一起：

- **tombstone**：删除标记是什么，为什么必须存在
- **TTL**：过期语义如何实现，为什么与修复/compaction 强耦合
- **回收**：何时可以真正丢弃旧值与 tombstone（GC 条件）

---

## 1. 为什么删除要写 tombstone

在 LSM 中，写入是追加新版本。删除通常表示：

```
Put(key, tombstone, version=v_del)
```

读路径遇到 tombstone，就认为 key 不存在（或已删除）。

如果没有 tombstone，而是“直接删掉某个文件里的旧值”，会立刻遇到两个问题：

- 旧值可能在更低层（更老的 SST）仍然存在，读会把它读出来
- 多副本系统里，某些副本没收到删除，后续修复会把旧值回补回来

工程结论：**tombstone 是删除语义的唯一可靠载体**。

---

## 2. tombstone 的传播：删除必须像写一样走复制协议

删除是写入的一种，需要：

- 有版本（可比较新旧）
- 走 quorum / 写路径
- 参与修复（read-repair / anti-entropy）

否则会出现经典事故：“删了又回来”。

一个常见复活路径：

```
Replica A: received tombstone
Replica B: missed tombstone (temporarily down)
Later read hits B -> sees old value
Repair pulls old value from B -> spreads it -> resurrection
```

修复机制必须把 tombstone 视作“比旧值更新”的版本。

---

## 3. TTL：过期不等于删除

TTL 的两种常见实现：

### 3.1 value 携带过期时间（read-time check）

value 中存 `expire_at`，读时判断：

- 如果已过期，读返回 NotFound（或逻辑删除）
- 物理回收交给后台 compaction/GC

优点：写路径简单；缺点：过期 key 仍占空间，且读路径要做判断。

### 3.2 TTL 变成 tombstone（write-time/scan-time materialize）

在后台扫描或 compaction 时把过期 key 物化成 tombstone：

优点：删除语义统一；缺点：后台需要扫描/判断，且要处理与修复并发。

工程上常见做法是“读时判断 + compaction 回收”的组合。

---

## 4. 何时可以真正丢弃 tombstone：GC 条件

tombstone 不能永久保留，否则空间会被删除历史占满。真正丢弃的条件与系统一致性模型强耦合。

### 4.1 单机 LSM（无复制）

当 compaction 确认：

- 更低层（更老）的所有 SST 范围都被覆盖
- 且该 key 的更老版本不可能再被读到

就可以丢弃 tombstone 并回收空间。

### 4.2 多副本系统：必须考虑“落后副本”

如果某副本长期落后，仍可能持有旧值：

- 一旦 tombstone 被 GC 掉
- 落后副本恢复后，通过修复把旧值带回来

因此需要一个“安全窗口”或“全副本可见性”条件：

- **基于时间的窗口**：tombstone 保留至少 `gc_grace_seconds`
- **基于版本的确认**：确认所有副本都已经看到 tombstone（更难，但更精确）

时间窗口的意义：给 anti-entropy 足够时间把删除传播到所有副本。

---

## 5. `gc_grace_seconds` 的工程权衡

窗口设得太小：

- 删除传播不完就 GC → 复活风险

窗口设得太大：

- tombstone 积累 → compaction 读写放大上升
- 空间占用上升

设置窗口时必须参考：

- 副本最大离线时长（维护/故障）
- 修复周期（anti-entropy 的覆盖周期）
- 修复带宽（backlog 是否可被清空）

建议配套指标：

- 每分片 tombstone 数量与占用空间
- 修复 backlog 与最大落后版本（lag）
- tombstone GC 速率与 compaction 写放大

---

## 6. compaction 与 tombstone：放大与尾延迟

tombstone 会影响 compaction：

- tombstone 需要被下推到更低层，才能覆盖更老版本
- 在下推过程中，compaction 会重写大量数据

因此删除密集场景可能出现：

- 写放大上升
- compaction backlog 增加
- 写 stall / 读延迟抖动

常见应对：

- 分表/分 CF：把 TTL/删除密集的数据隔离，避免污染主数据
- 调整 compaction 策略：降低 backlog，平滑 IO
- 对 tombstone 做聚合：同一范围的大量删除可用 range tombstone（如果引擎支持）

---

## 7. 小结

删除语义的稳定性依赖三件事同时成立：

- tombstone 是“真正的删除”
- tombstone 必须走复制协议并被修复传播
- tombstone 的 GC 必须满足“所有副本都已收敛”的安全条件（时间窗口或版本确认）

TTL 只是“自动产生删除”的一种来源；如果把 TTL 当作读时过滤而不做一致性传播，最终仍会回到“删了又回来”的老问题。

