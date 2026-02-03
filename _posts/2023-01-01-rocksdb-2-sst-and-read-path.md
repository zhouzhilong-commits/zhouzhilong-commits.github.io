---
layout: single
title: "RocksDB（2）：SST 结构与读路径（Table/Block/Index）"
series: rocksdb
tags: [RocksDB]
---

这一篇聚焦 RocksDB 的 **SST（Sorted String Table）**：一个 SST 里大致有什么，以及一次点查通常会经历哪些步骤。

![SST（Table File）结构：Data/Index/Filter 的关系](/images/diagrams/rocksdb-sst-structure.svg)

## 1. SST 解决什么问题

SST 本质上是“磁盘上的有序 KV 文件”，它让：

- flush 能顺序写出一个有序文件
- 读路径可以做二分查找 + block 粒度读取

## 2. 可以将 SST 理解成三层

- **Data blocks**：真正存 KV 数据（通常是压缩后的 block）
- **Index blocks**：告诉你某个 key 大概在哪个 data block
- **Filter blocks**（例如 Bloom Filter）：帮助快速判断 key 是否可能在该文件里

所以一次点查的理想路径是：

1. 先用 filter 排除大部分“不在这个文件里”的情况
2. 用 index 定位到目标 data block
3. 只读取 1 个或少量 data block

### 2.1 为什么“只读 1 个 block”是理想状态

对点查来说，尾延迟往往由随机 IO 决定；所以你希望：

- 先用 filter 排除掉绝大多数不相关文件（特别是负查）
- 用 index 把定位范围缩小到 1 个 block

只要你需要读多个文件/多个 block，尾延迟通常会明显变差（并且更难稳定）。

## 3. 读路径为什么会变慢

常见原因：

- 文件数太多（读放大增加）
- filter 命中差（假阳性过高或没有 filter）
- cache 没命中（block cache / page cache）

### 3.1 更可落地的排查顺序

1. **文件数/层数**：L0/L1 是否堆积（读要查更多文件）？
2. **filter 是否有效**：负查是否仍然触发大量 IO（假阳性过高/没开 filter）？
3. **cache 命中**：至少拆开看 data/index/filter 的命中（别只看总体）。
4. **IO vs CPU**：NVMe 上经常是“解压/校验/迭代器合并”吃 CPU；HDD/远端更像 IO 瓶颈。

后续我们会在“读放大”与“compaction”那一篇把这些原因串起来。

