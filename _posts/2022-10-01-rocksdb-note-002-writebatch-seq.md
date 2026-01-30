---
layout: single
title: "RocksDB 笔记：WriteBatch 与 seq：一次写入如何变成原子批次"
series: rocksdb
categories: [storage]
tags: [存储, RocksDB]
permalink: /rocksdb-note-002-writebatch-seq/
---
这篇讲清楚两件事：

- **WriteBatch**：把多次 Put/Delete 合成一次写入（从“业务事务视角”看更自然）。
- **sequence number（seq）**：让“写入可见性/顺序/原子性”变得可定义、可推理。

![WriteBatch 与 seq：原子批次、可见性与确认点](/images/diagrams/rocksdb-writebatch-seq-atomicity.svg)

## 1. 你为什么会关心 WriteBatch / seq

线上常见触发点：

- **你想要“要么全写入、要么全不写入”**：例如写一条主记录 + 两个索引更新；或者 Put 新值同时 Delete 旧 key。
- **你遇到“读到了半套数据”**：多 key 更新没有原子边界，读端在更新中间切入。
- **你在 debug“乱序/覆盖”**：同一个 key 连续写，多线程并发下到底谁赢？读到的是哪次写？

一句话：**WriteBatch 提供“原子边界”，seq 提供“全局顺序”**（以 DB 为单位）。

## 2. 核心模型：用 4 个概念把写入讲清楚

- **Batch**：一个 write request 里包含 N 个操作（Put/Delete/Merge...）。
- **seq（序列号）**：给写入打一个单调递增的编号；读的时候“以 seq 为时间线”做可见性判断。
- **确认点（durability）**：`WriteOptions.sync` 决定“返回成功时”是否已经 fsync。
- **可见性（visibility）**：成功写入后，通常会在 MemTable 可见；持久化则取决于 WAL 的确认点。

## 3. 机制拆解：一次 WriteBatch 到底发生了什么（高层）

你可以把它当成下面这个最短闭环：

1. **给 batch 分配一个起始 seq**（比如 `seq = S`）。
2. batch 内的第 i 个操作，逻辑上对应 `S + i`（实现上可能通过 encode/iterate 实现）。
3. **写 WAL（追加）**：把 batch 编码后写入日志（`sync` 可选）。
4. **写 MemTable**：把 batch 拆成多条 key-value / tombstone 插入内存结构。
5. `Write()` 返回：此时**可见性**通常成立；**可恢复性**取决于 WAL 的确认策略。

### 3.1 “原子”是什么意思：对读端的承诺

业务在乎的通常不是“物理上一步完成”，而是**读端是否会看到“半套更新”**。

- 如果读操作是“以某个 seq 作为 snapshot”，那么它要么看到更新前，要么看到更新后（不会看到中间态）。
- WriteBatch 的价值在于：它给“多 key 更新”提供了一个可描述的边界（配合 snapshot/事务层，才能真正做到强语义）。

> 注意：不同读 API（是否使用 snapshot）会影响你能得到的语义；不要把“单 key 读到新值”误当成“多 key 原子可见”。

## 4. 你会在系统里看到的现象（可观测信号）

当 write path 出问题时，WriteBatch/seq 往往体现在这些地方：

- **WAL 变大、fsync 变慢**：batch 更大 → 单次写入更重；同时 group commit 会改变延迟分布。
- **写放大上升**：batch 合并能减少用户态调用次数，但 flush/compaction 仍可能主导总写入量。
- **尾延迟变“批次化”**：batch 的边界会让 ack 更像“成批确认”。

## 5. 工程建议：怎么用好 WriteBatch

- **把“逻辑事务”做成 batch**：主记录 + 索引更新尽量同批（否则你要自己处理崩溃恢复/补偿）。
- **不要为了吞吐盲目变大**：batch 过大可能拉高 P99（尤其当你开启 sync 或磁盘抖动时）。
- **明确一致性目标**：
  - 只要“单 key 最终正确”：写后读一般就够。
  - 需要“多 key 强一致”：读侧必须使用 snapshot/事务语义（否则中间态依然可能被看到）。

## 6. 最小排障清单（按优先级）

1. **确认写入语义**：`sync` 是否打开？是否有 group commit？业务能接受多大崩溃窗口？
2. **确认读语义**：读侧是否用了 snapshot/事务？是否存在“读到中间态”的可能？
3. **确认 batch 大小分布**：平均很小但偶发巨大（会直接制造 tail latency）。
4. **看 WAL/fsync 延迟分布**：尾延迟是否被磁盘确认点主导？

## 7. 参考

- RocksDB Wiki / Blog：Write path、WriteBatch、WAL（以你的版本为准）
- 任何线上排障都建议把“语义 → 指标 → 实验”闭环跑一遍：先定义承诺，再验证事实。

