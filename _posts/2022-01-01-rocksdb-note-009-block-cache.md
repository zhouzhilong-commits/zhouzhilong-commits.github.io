---
layout: single
title: "RocksDB 笔记：Block Cache：缓存什么、怎么估算命中"
series: rocksdb
categories: [storage]
tags: [存储, RocksDB]
permalink: /rocksdb-note-009-block-cache/
redirect_from:
  - /rocksdb-note-030-block-cache/
---
这篇笔记更“贴近工程现场”地回答 RocksDB 的一个高频问题：**Block Cache 到底缓存什么？怎么估算需要多大？为什么“命中率看起来不低”但延迟还是很差？**

![RocksDB 读路径上的 Block Cache：命中与未命中的差别](/images/diagrams/rocksdb-block-cache-path.svg)

## 1. 背景：这个问题通常在什么场景出现

- **读多写少的 KV 服务**：读延迟（尤其 P95/P99）成为主矛盾，想用缓存把随机 IO 压下去。
- **写多读也多的混合负载**：Compaction 吃资源导致 cache 竞争，出现“平时快、偶发抖”的尾延迟。
- **负查（key 不存在）很多**：Bloom filter/索引块命中能省大量 IO，但 data block miss 仍然会让“存在的 key”变慢。
- **数据压缩开启**：cache 命中不仅省 IO，还省解压/校验的 CPU；反过来 miss 会放大 CPU 压力。

> 目标最好可量化：例如 `P99 read latency < 5ms`、`device read bytes/s` 降到某阈值、或 `block cache data hit rate` 达到某区间。

## 2. 核心概念：用最少概念把模型搭起来

这里用 6 个概念把模型搭起来（够用、且可落地）：

- **Block**：SST 的最小 IO 单元（通常 4KB~16KB/64KB，具体看配置/数据分布）。
- **三类可缓存块**：
  - **data block**：真正的 KV 数据（通常占 cache 的大头，也是决定读性能的关键）。
  - **index block**：把 key range 映射到 data block handle（更小、更容易被 cache）。
  - **filter block（Bloom）**：快速判断“这个文件是否可能包含 key”（对负查收益巨大）。
- **命中/未命中成本差**：
  - 命中：内存读 + 少量解析（非常稳定）
  - 未命中：随机 IO + 校验 +（可能）解压 + 插入 cache（尾延迟显著更差）
- **工作集（working set）**：真正“频繁被读”的数据集合（不等于总数据量）。
- **驱逐（eviction）**：cache 装不下工作集时就会频繁淘汰，导致“抖”。

> 经验：你追求的通常不是最高平均命中率，而是**稳定的 data block 命中**（尤其热点表/热点 key-range）。

## 3. 机制拆解：为什么会发生（因果链）

把它拆成“输入 → 路径 → 现象”的链路（每一项都能在指标里验证）：

- **输入**
  - 点查 vs 范围扫：范围扫更容易触发顺序读/预取，但也更容易把 cache 冲掉
  - 读 key 分布：Zipf（热点明显）通常更“适合 cache”，均匀分布则更难命中
  - value 大小：value 很大时，单个 data block 里有效数据比例会变差
- **路径**
  1. 先查 MemTable/Immutable（命中则无需落盘读）
  2. 对每个候选 SST：先 filter（可能）→ index 定位 → data block 读
  3. data block 读完：校验/解压 → 放入 cache（下次命中）
- **现象**
  - `index/filter` 命中不错，但 `data` 命中差 → 看起来“有 cache”，但延迟仍差
  - compaction 高峰时命中率下降 → cache 与后台读写争抢内存/IO

### 3.1 为什么“命中率不低”但还是慢（最常见的坑）

你需要区分三种命中率：

- **Block cache hit rate（总体）**：可能被 index/filter 撑高
- **Data block hit rate（关键）**：决定大部分读 IO
- **Read latency 的 P99**：最终用户体验，受 miss 的尾部影响更大

如果你只盯总体 hit rate，很容易误判。

## 4. 工程权衡：优化通常会带来什么副作用

把 cache 调大/调小，真正的权衡在这里：

- **Block cache vs MemTable**：cache 太大挤压 memtable，会更频繁 flush/compaction，反而把读写都拖慢。
- **Cache vs OS page cache**：你同时拥有文件系统 page cache；两者叠加可能浪费内存，也可能互补（取决于压缩/读形态）。
- **范围扫描污染**：scan 很容易把热点挤出 cache，需要隔离（例如 scan 不进 cache / scan 专用策略）。
- **压缩与 CPU**：cache 命中能省解压；但如果 CPU 已经满，miss 会更致命。

## 5. 排查清单（建议按顺序）

1. **拆开看命中**：至少区分 `data/index/filter` 的命中（不要只看总体）
2. **看 miss 成本**：miss 时每次读要触碰多少 SST？是否伴随大量负查？
3. **看 cache 驱逐**：是否频繁 eviction？是否出现短时间内命中率断崖式下降？
4. **看后台干扰**：compaction 期间读延迟是否同步抬头？是否有 write stall？
5. **看资源与瓶颈**：
   - 设备随机读延迟/队列深度
   - CPU（解压/校验）是否打满
   - 内存是否发生频繁 GC/换页（如果你在 JVM/容器环境）

## 6. 小结

Block Cache 的核心不是“把 hit rate 调到最高”，而是：

- 让 **data block 命中** 足够稳定
- 让 **miss 的尾部成本** 可控（减少需要触碰的文件数/层数）
- 在 **memtable / cache / compaction** 之间做整体预算

下一步如果你愿意，我们可以把这篇继续补到“更硬核”的程度：加入 RocksDB 常用统计项（tickers/histograms）的对照表，以及一个按 workload 估算 cache size 的示例（从工作集和 block 大小推算）。

