---
layout: single
title: "RocksDB 笔记：压缩与校验：CPU/IO 的权衡点"
series: rocksdb
categories: [storage]
tags: [存储, RocksDB]
permalink: /rocksdb-note-016-cpu-io/
---

本文是「RocksDB 笔记：压缩与校验：CPU/IO 的权衡点」的工程化笔记，记录语义/模型定义、可观测信号与排障要点。

![RocksDB 笔记：压缩与校验：CPU/IO 的权衡点](/images/diagrams/cpu-vs-io-bound.svg)
## 1. 这篇到底想解决什么：别把“变慢”都归因给 IO

RocksDB 的常见误判是：

- 看到写入/读延迟上升，就认为是“盘慢了”
- 看到 NVMe 很快，就认为“IO 不可能是瓶颈”

实际更常见的是：瓶颈会在不同阶段切换——尤其在启用压缩/校验、以及写入高峰触发 flush/compaction 时。

## 2. 三类最常见瓶颈：CPU / IO / 锁（以及它们的信号）

### 2.1 CPU-bound（压缩/校验/解析开销主导）

典型信号：

- CPU 利用率高（更关键是 **per-core**）
- IPC 低或 cycles 高（cache miss/branch miss/前端瓶颈）
- 压缩/校验相关函数在 profile 中占比高

常见诱因：

- 压缩算法过重（或压缩级别过高）
- checksum/verify/解压在热路径上
- 小 IO + 高并发导致 CPU 侧开销被放大

### 2.2 IO-bound（设备/队列化/后台抢占主导）

典型信号：

- IO 延迟分位数抬头（P99/P999），并且呈现队列化特征
- fsync/journal/page cache 回写导致周期性长尾
- compaction/flush/backlog 欠账持续上升

常见诱因：

- 设备抖动或共享盘 noisy neighbor
- 后台任务抢占（compaction/rebuild/备份）
- 近满盘导致 GC/写放大上升（SSD/FTL 也会抖）

### 2.3 锁/同步开销（并发扩展性瓶颈）

典型信号：

- CPU 没满但吞吐上不去，延迟上升
- profile 中出现大量 lock/condvar/atomic 自旋
- 增加线程数反而更慢（争用放大）

常见诱因：

- 热点列族/热点 key 导致内部争用
- 写入路径 group commit/队列化实现导致竞争点显著

## 3. 一个非常实用的“先分桶再细化”排障顺序

1. **先看现象属于读还是写**：读慢常见是读放大/cache/compaction；写慢常见是 flush/L0/backlog 与确认点（fsync）。
2. **再分桶 CPU/IO/锁**：
   - IO：看延迟分位数与队列、backlog
   - CPU：看 per-core、IPC/cache/branch、压缩/校验占比
   - 锁：看争用与扩展性（线程越多越慢）
3. **做最小 A/B 验证因果**：
   - 临时关闭/降低压缩（验证 CPU）
   - 临时降低写入或提高后台预算（验证 IO/backlog）
   - 限制并发或改变 workload（验证锁争用）

## 4. 压缩与校验：它们把瓶颈从 IO 推向 CPU（但可能是好事）

压缩/校验本质上是在做交换：

- 用 CPU 换 IO（减少写入字节/读盘字节）
- 换来的收益取决于：当前是 IO-bound 还是 CPU-bound

实践中常见两种极端：

- **SATA/远端盘**：压缩往往很值（IO 更贵）
- **NVMe**：压缩可能把系统推到 CPU-bound，需要谨慎选算法与级别

## 5. 小结

RocksDB 的性能问题最怕“盲猜”。先把瓶颈分成 CPU/IO/锁三类，再用最小 A/B 验证因果，调参才会变成工程而不是玄学。
