---
layout: single
title: "RocksDB 笔记：MemTable/Immutable：写入高峰的内存结构演进"
series: rocksdb
categories: [storage]
tags: [存储, RocksDB]
permalink: /rocksdb-note-044-memtable-immutable/
redirect_from:
  - /rocksdb-note-023-memtable-immutable/
---

本文是「RocksDB 笔记：MemTable/Immutable：写入高峰的内存结构演进」的工程化笔记，记录语义/模型定义、可观测信号与排障要点。

![RocksDB 笔记：MemTable/Immutable：写入高峰的内存结构演进](/images/diagrams/rocksdb-write-path.svg)

## 1. 最短闭环：MemTable 是“写入缓冲”，Immutable 是“欠账队列”

写入路径最短闭环可以这样理解：

1. 写 WAL（决定“可恢复语义”）
2. 写 **mutable memtable**（内存有序结构，写入可见性通常从这里开始）
3. memtable 写满后变成 **immutable memtable**（不再接收写，只等后台 flush）
4. 后台 **flush** 把 immutable 落盘为 SST（通常先落到 **L0**）
5. 后台 **compaction** 把 L0/L1… 逐步合并，控制读放大并回收空间

核心要点：**immutable 的数量就是你“写入欠账”的体感指标**。immutable 一直堆，就等于 flush 跟不上写入速度。

## 2. MemTable 相关的 3 个“必须搞清楚”的问题

### 2.1 MemTable 什么时候切换（mutable → immutable）？

直觉上是 “写满了就切”，但工程上影响切换节奏的因素很多：

- `write_buffer_size`（单个 memtable 的预算）
- `max_write_buffer_number`（允许同时存在多少个 memtable）
- 写入形态（小写多、热点 key、多列族等会改变内存增长速度）

### 2.2 Immutable 什么时候会导致写入被限速/阻塞？

如果 immutable 持续增长，RocksDB 会启动保护：

- **throttle**：还能写，但限速
- **stall**：直接卡写（保护系统不崩）

触发细节与版本/配置有关，但从排障角度可以将它当成一个信号：

> **如果 immutable 堆积到了触发保护的阈值，说明 flush/compaction 已经欠账到危险程度。**

### 2.3 为什么 “memtable 欠账” 会很快变成 “L0 欠账”？

flush 的输出通常是 L0 文件。L0 文件数上升会带来两个问题：

- 读放大变差（L0 文件相互重叠，读需要查更多文件）
- compaction 压力上升（L0→L1 的合并变频繁，抢占 IO/CPU）

所以 memtable/immutable 的问题经常会沿着链路传导成：

> immutable ↑ → flush 频繁 → L0 文件 ↑ → compaction 欠账 ↑ → 写入抖动/卡写

## 3. 会在系统里看到什么：从最有用信号开始

建议优先看这些“中间量”，它们最能证明因果链：

- **immutable memtable 数量 / 占用内存**：是否持续上升？是否周期性堆高？
- **flush 速率与耗时分布**：flush 是否出现长尾？是否被 IO/CPU 卡住？
- **L0 文件数 / L0 size**：是否持续上升并接近阈值？
- **compaction backlog**：是否在追债？追不动就会把写入拖进抖动
- **stall/throttle 次数**：保护是否频繁触发？

## 4. 常见根因（按出现频率排序）

1. **设备或文件系统写入抖动**：flush 需要写 SST + 元数据，遇到 fsync/journal 抖动会直接长尾。
2. **后台任务抢占**：compaction/repair/备份/重建抢 IO，flush 被挤压。
3. **CPU 成为瓶颈**：压缩/校验让 flush/compaction 在 NVMe 上反而更可能 CPU-bound。
4. **写入峰值太尖**：平均 OK，但突发写入把 write buffer 吃光，immutable 堆积后触发保护。

## 5. 一个很稳的排障顺序（先归因，再调参）

1. **先判定欠账发生在哪**：immutable 堆积（flush 跟不上）还是 L0/backlog 堆积（compaction 跟不上）？
2. **看资源瓶颈**：flush/compaction 慢，是 IO 慢还是 CPU 慢？
3. **做最小 A/B**：
   - 临时提升 flush/compaction 预算（线程/带宽）看欠账是否下降
   - 临时降低写入（限流）看系统是否恢复稳态
4. **最后再动参数**：把 write buffer 当“缓冲器”，把后台预算当“还债能力”，别用参数掩盖根因。

## 6. 和另外两篇的关系（建议联读）

- 如果看到 **L0 文件持续上升**，下一篇建议看：`rocksdb-note-065-flush-write-buffer-l0`
- 如果你已经出现 **write stall**，建议看：`rocksdb-note-058-write-stall`
