---
layout: single
title: "存储笔记：tombstone 与空间回收：为什么删除不等于释放"
series: storage_basics
categories: [storage]
tags: [存储, 存储基础系列]
permalink: /storage-note-071-tombstone/
redirect_from:
  - /storage-note-015-tombstone/
  - /storage-note-043-tombstone/
---
本文讲清楚一个容易误解的事实：在很多存储系统（尤其 LSM）里，**Delete 并不等于空间立刻释放**。删除本质上是“写入一个 tombstone（删除标记）”，真正回收空间通常发生在后台 compaction/GC 之后。

![tombstone 生命周期：删除可见 ≠ 空间回收](/images/diagrams/tombstone-compaction-lifecycle.svg)

## 1. tombstone 是什么

- **语义**：对某个 key 写入一个“删除标记”，让读路径把它当作“不存在”。
- **目的**：在多层/多文件/多版本的系统里，删除需要一个“可合并的事实”，否则你很难在不扫描全量数据的情况下让删除生效。

## 2. 为什么“删了还占空间”

因为旧版本通常还在 SST/段文件里：

- tombstone 只是覆盖在“更高层/更新的版本”上，让读看到删除
- 旧版本要等到 compaction 把它合并淘汰（或者 GC 回收）才会真正释放空间

所以“删除多 + compaction 跟不上”时，会观察到：**盘持续增长、写放大上升、读放大也可能变差**。

## 3. 什么时候空间会真正回收

一般需要满足：

- tombstone 被 compaction 处理到足够“深”（到达能覆盖旧版本的层级/范围）
- 或者达到某些安全条件（例如没有更旧层还可能出现该 key 的版本）

不同实现会有不同的“删标回收规则”，但共同点是：**回收是异步的**。

## 4. 排查清单（需要看什么）

1. **删除比例**：写入里 delete/overwrite 的占比是否变高？
2. **compaction backlog**：pending bytes、L0 文件数、stall/throttle 是否上升？
3. **空间放大**：实际磁盘占用 vs 逻辑数据量是否持续拉大？
4. **读放大信号**：文件数/层数是否增加（导致读路径更复杂）？

## 5. 小结

tombstone 让删除“立刻可见”，但空间回收取决于后台合并是否跟上。线上优化通常不是“多删”，而是**让后台预算可控 + 合并策略匹配负载**。

