---
layout: single
title: "RocksDB 笔记：Flush 触发条件：write buffer 与 L0 文件数量"
series: rocksdb
categories: [storage]
tags: [存储, RocksDB]
permalink: /rocksdb-note-065-flush-write-buffer-l0/
---
你在 RocksDB 写入链路里，最容易遇到两类“看似突然”的现象：

- 写入延迟开始抖（P99 上升）
- 甚至出现 **write stall / throttle**（写被限速或阻塞）

它们经常不是 WAL 的锅，而是这条链路欠账了：

> **write buffer（memtable）→ flush 产生 L0 → L0 触发 compaction**

![RocksDB：write buffer / flush / L0 / stall 的关系](/images/diagrams/rocksdb-flush-l0-stall.svg)

## 1. 先把术语对齐：write buffer / memtable / flush / L0

- **memtable**：内存中的写入缓冲（通常是有序结构），写入先落这里。
- **write buffer**：你可以把它理解成 memtable 占用的预算（受 `write_buffer_size`、memtable 数量等影响）。
- **flush**：把 immutable memtable 持久化为 SST 文件（通常落到 **L0**）。
- **L0**：RocksDB 分层里的第 0 层，文件之间可能重叠，读放大敏感，也容易引发后续 compaction 压力。

## 2. 为什么会出现 L0 堆积：这是“后台欠账”的最直接信号

当写入速度 > flush + compaction 的后台能力时，就会出现：

1. memtable 频繁转 immutable
2. flush 不断生成 L0 文件
3. L0 文件数上升，读放大变差
4. compaction 跟不上，进一步挤占 IO
5. 最终触发写入限速/阻塞（保护系统）

这是一条典型的“雪球链”：**越欠账，越抖；越抖，越欠账**。

## 3. 写入为什么会 stall：两道“保险丝”

RocksDB 需要保证自己不会把系统写爆或把读拖垮，所以常见有两类保护动作：

- **write throttle**：还能写，但限速（更像“踩刹车”）。
- **write stall**：直接卡写（更像“停车”）。

触发点通常与两类资源有关：

- **memtable/immutable 太多**：flush 跟不上。
- **L0 太多**：compaction 跟不上（且 L0 对读放大影响大）。

## 4. 你应该看哪些指标（从最有用的开始）

建议优先盯这几类“因果链中间量”：

- **immutable memtable 数量**：是否持续上升？
- **L0 文件数量 / L0 size**：是否持续上升？是否触顶？
- **compaction backlog / pending bytes**：后台是否欠账？
- **flush/compaction 的吞吐与耗时分布**：是否出现长尾？
- **stall/throttle 次数**：是否频繁触发保护？

> 经验：如果你只看“磁盘利用率/IOPS”，很容易误判。关键是 **队列化 + 欠账**。

## 5. 怎么调：不要从“参数”开始，要从“瓶颈归因”开始

先问两个问题：

- **flush 慢** 还是 **compaction 慢**？
- 主要瓶颈是 **IO** 还是 **CPU（压缩/校验）**？

### 5.1 flush 跟不上：你在“攒 immutable”

常见策略：

- 适当增大写入缓冲预算（例如调 `write_buffer_size`、可用 memtable 数量）以吸收短峰值
- 提升 flush 并行/预算（取决于你的 RocksDB 版本与配置项）
- 避免让后台任务与前台争抢同一块 IO（尤其是在 compaction 也很重时）

### 5.2 compaction 跟不上：你在“攒 L0”

常见策略：

- 给 compaction 足够资源预算（线程/带宽），否则它永远在追债
- 让 L0 的压力不要无限累积（否则读放大和写抖动都会一起恶化）
- 如果压缩很重：确认 CPU 是否已经成为瓶颈（NVMe 上经常如此）

## 6. 一套最小实验：10 分钟确认“是谁欠账”

1. 固定 workload，记录一段时间：
   - immutable 数量
   - L0 文件数
   - compaction backlog
   - P99 写入延迟
2. **只提升 flush 能力**（例如增加 flush 线程/预算）观察 L0 变化
3. **只提升 compaction 能力**观察 L0 与 P99 的变化

你会很快知道：到底是 flush 还是 compaction 主导欠账。

## 7. 最小排障清单（线上写入变慢/变抖）

1. **先看 L0 与 backlog**：是否在持续上升？
2. **再看 immutable**：是否在堆积？
3. **确认是不是后台任务抢占**：compaction/flush 是否把 IO/CPU 打满？
4. **最后才谈调参**：先归因再调整，不要“玄学”改一堆参数。

## 8. 小结

write buffer、flush、L0 本质是一条“后台债务链”。只要你能把“欠账信号”观测出来（immutable/L0/backlog），写入抖动问题通常就能从“感觉”变成“可解释、可验证”的工程问题。

