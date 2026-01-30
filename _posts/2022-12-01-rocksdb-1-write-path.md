---
layout: single
title: "RocksDB（1）：写入链路（WAL + MemTable）"
series: rocksdb
tags: [RocksDB]
---

这篇作为 RocksDB 系列的第 1 篇，先把「一次 `Put()/Write()` 从 API 到落盘语义」讲清楚：**写入路径、确认点（durability）、以及写入抖动来自哪里**。后续再分别展开 SST、读路径与 compaction 调参。

![RocksDB 写入路径（抽象版）](/images/diagrams/rocksdb-write-path.svg)

## 1. 一次写入的最短闭环

从工程视角看，一次写入至少要满足：

- **快速**：能承受高并发写入
- **可恢复**：崩溃后不能丢“已经返回成功”的写入

因此 RocksDB 的典型路径是：

1. 写 **WAL（Write-Ahead Log）**
2. 写入 **MemTable**（内存中的有序结构）
3. 触发 **Flush**：把 MemTable 变成 SST 文件
4. 后台 **Compaction**：合并多个 SST，回收空间并控制读放大

### 1.1 写入里最容易被忽略的点：写入“什么时候可见/可恢复”

同样是 `Put()` 返回成功，不同配置/实现的语义可能不同：

- **写入可见**：MemTable 中可读到（通常很快）
- **写入可恢复**：WAL 已经持久化到磁盘（取决于 sync/group commit）

很多线上系统会做：`WriteOptions.sync=false` + group commit（更高吞吐），并接受一个小的崩溃丢数据窗口（由业务决定）。

> 记住一句话：**“返回成功”到底意味着什么**，不是 RocksDB 帮你决定的，而是由你的 `WriteOptions` + 业务容忍度共同决定的。

## 2. WAL：持久性与 group commit

WAL 的存在让系统能在崩溃后通过重放恢复 MemTable 的状态。

你在使用时会遇到的关键点：

- `sync`/`fsync` 决定持久性强度（更强通常更慢）
- **group commit** 可以把多次写合并成一次 fsync，降低尾延迟

![group commit：把多次 fsync 合并成一次](/images/diagrams/wal-group-commit-timeline.svg)

### 2.1 你会在性能上看到什么

- **sync 打开**：平均延迟上升，尾延迟更敏感（更“跟磁盘走”）
- **sync 关闭 + group commit**：吞吐更高，但崩溃窗口更大；高峰期仍可能被 flush/compaction 影响

### 2.2 一些非常实用的“写入语义”检查题

- **Q1：`Put()` 成功后立刻读，是否必须读到？**
  - 通常是“是”（写入已在 MemTable 可见），但跨 DB 实例/跨进程/跨节点就变成系统级一致性问题了。
- **Q2：`Put()` 成功后立刻断电，是否必须保住？**
  - 取决于 `sync`；`sync=false` 时你需要接受“丢一个批次”的窗口。
- **Q3：我看到 P99 抖动，但平均延迟还行，最可能是什么？**
  - 常见是 fsync/flush/compaction 的竞争、write stall/throttle，或 IO 抖动放大到了确认点上。

## 3. MemTable：写入快但不是“免费”

MemTable 让写入先落在内存里，代价是：

- 内存占用（多个 memtable + immutable memtable）
- 触发 flush 后会产生 SST（开始进入“后台写放大”的链路）

### 3.1 Immutable 队列：写高峰为什么会“堆起来”

写入高峰时，MemTable 会不断转成 immutable，等待后台 flush。

如果 flush 跟不上，你会看到：

- immutable 数量上升
- L0 文件数上升（读放大也会变差）
- 最终触发 write stall / throttle（保护系统不崩）

## 4. 写入抖动通常从哪里来（你该先盯什么）

从“可解释的工程现象”出发，写入抖动最常见的来源是：

- **确认点跟着 fsync 抖**：磁盘/文件系统/虚拟化 IO 抖动直接放大到写入延迟。
- **flush 跟不上**：immutable 堆积，最终触发 stall/throttle。
- **compaction 欠账**：L0/L1 堆积、后台重写占满 IO 带宽，写入被迫限速。

## 5. 你可以关注的两个“核心指标” + 两个“更实用的信号”

为了后面理解性能：

- **写放大**：WAL + flush + compaction 会带来额外写入
- **读放大**：层级越多、文件越多，读路径越复杂

### 4.1 再补两个“更实用”的信号

- **write stall/throttle 次数**：是否在用“卡写”换稳定
- **compaction backlog**：后台是否已经欠账（欠账越多，越容易抖）

## 6. 一个最小排障顺序（遇到写入变慢/变抖时）

1. **先确认写入语义**：`sync` 到底开没开？是否有 group commit？业务能接受多大窗口？
2. **再看是否“欠账”**：immutable/L0/compaction backlog 是否持续上升？
3. **最后再看资源**：IO 利用率、fsync 延迟分布、CPU 是否被压缩/校验打满。

下一篇我们会从 **SST 文件结构** 切入：SST 里面的 block / index / filter 是怎么组织的，读路径为什么能做到“尽量少读”。

