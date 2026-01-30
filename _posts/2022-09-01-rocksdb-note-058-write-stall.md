---
layout: single
title: "RocksDB 笔记：Write stall：为什么会卡住、如何定位"
series: rocksdb
categories: [storage]
tags: [存储, RocksDB]
permalink: /rocksdb-note-058-write-stall/
redirect_from:
  - /rocksdb-note-037-write-stall/
---

本文围绕「RocksDB 笔记：Write stall：为什么会卡住、如何定位」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![RocksDB 笔记：Write stall：为什么会卡住、如何定位](/images/diagrams/rocksdb-flush-l0-stall.svg)
## 1. write stall 的本质：系统在“欠账过多”时强制刹车

write stall（或 write stop）通常不是“写路径坏了”，而是 RocksDB 在保护自己：

- flush/compaction 追不上写入
- L0 文件堆积导致读放大恶化
- 内存/磁盘/后台队列接近危险线

于是系统选择：**宁可卡写，也不要把整个实例拖到不可恢复的抖动里**。

你可以把它理解成写入链路上的“保险丝”。

## 2. 一张根因树：stall 一般是这三类欠账之一

### 2.1 MemTable/Immutable 欠账（flush 跟不上）

典型信号：

- immutable 数量持续上升
- memtable 相关内存占用持续上升
- flush 变慢或 flush 线程/队列被挤压

直觉：写入把“内存缓冲”吃光了，系统只能卡写等待 flush 把欠账还掉。

### 2.2 L0 欠账（flush 产出太多，L0→L1 compaction 跟不上）

典型信号：

- L0 文件数持续上升（或 L0 size 持续上升）
- compaction backlog 持续增长
- 读放大指标变差（读路径需要触碰更多文件）

直觉：flush 很勤快，但 compaction 还债能力不足，L0 堆成“炸弹”。

### 2.3 compaction 欠账（整体还债能力不足，进入“追债-抖动”循环）

典型信号：

- compaction backlog 长期高位
- compaction/flush 的耗时分位数出现长尾
- 写入 P99 抖动、且随时间逐步恶化

直觉：后台长期追不上，系统为了不崩只能频繁限速/卡写。

## 3. 线上最常见的“诱因”（按出现频率）

1. **IO 抖动或带宽不足**：fsync/journal/邻居噪声/存储队列化，让后台任务长尾。
2. **后台任务抢占**：备份、重建、scan、压缩、校验把 IO/CPU 吃掉。
3. **写入形态问题**：大量小写、热点 key、覆盖写多，导致 flush/L0 更频繁。
4. **CPU 成为瓶颈**：NVMe 足够快后，压缩/校验/锁竞争更容易成为主导。

## 4. 你应该先看哪些指标（从“最能证明因果”开始）

- **immutable memtable 数量**：是否持续上升？
- **L0 文件数 / L0 size**：是否持续上升并接近阈值？
- **compaction backlog**：是否在追债？是否越追越多？
- **flush / compaction 的耗时分位数**：是否出现长尾？
- **stall/throttle 次数与持续时间**：卡写是偶发还是长期？

## 5. 最小排障顺序（强烈建议按这个走）

1. **先判定是哪类欠账**：immutable 先堆？还是 L0/backlog 先堆？
2. **再判定瓶颈类型**：IO-bound 还是 CPU-bound？
3. **做最小 A/B**（验证因果）：
   - 临时减少写入（限流）看欠账是否下降
   - 临时提高后台预算（线程/带宽）看欠账是否下降
4. **最后再调参**：参数只能改变“缓冲器大小/触发点”，不能凭空制造后台能力。

## 6. 联读建议

- 你如果看到 immutable/L0 的增长链路：建议联读 `rocksdb-note-044-memtable-immutable` 与 `rocksdb-note-065-flush-write-buffer-l0`
- 你如果怀疑是 CPU/IO 判断错误：建议联读 `rocksdb-note-016-cpu-io`
