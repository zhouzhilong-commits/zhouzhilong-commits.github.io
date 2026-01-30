---
layout: single
title: "RocksDB 笔记：Bloom / Ribbon filter：降低负查的成本"
series: rocksdb
categories: [storage]
tags: [存储, RocksDB]
permalink: /rocksdb-note-051-bloom-ribbon-filter/
redirect_from:
  - /rocksdb-note-072-bloom-ribbon-filter/
---

本文围绕「RocksDB 笔记：Bloom / Ribbon filter：降低负查的成本」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![RocksDB 笔记：Bloom / Ribbon filter：降低负查的成本](/images/diagrams/bloom-filter-sizing.svg)
## 1. 先把问题说清楚：Bloom/Ribbon 优化的是“负查”（negative lookup）

很多线上读放大并不是“读到了很多数据”，而是“读了很多**本来就不存在**的 key”。负查的典型白跑链路是：

1. cache miss（或根本没有 cache）
2. 去 SST 查找：读 index/filter，甚至读 data block
3. 最后发现 key 不存在

Bloom/Ribbon 的工程语义就是：

> **尽可能在不读 data block（甚至不读文件）的前提下，快速判断“这个 SST 一定没有这个 key”。**

## 2. 三个关键量：bpk、假阳性、负查占比

### 2.1 bits-per-key（bpk）：你愿意用多少空间换少跑腿

bpk 越高：

- filter 更大（占更多空间，构建也更重一点）
- 假阳性率通常更低（更少白跑）

bpk 太低：

- 假阳性率上升
- 负查时仍会频繁触发无效 IO（尤其在 cache miss 时）

### 2.2 假阳性（false positive）：Bloom 的“唯一坏事”

Bloom 不会把存在的 key 判断为不存在；它唯一的坏事是 **假阳性**：把不存在的 key 误判为“可能存在”。

假阳性的代价取决于读路径：

- data block 多在 block cache：代价不大（多一次内存访问）
- cache miss 需要读盘：代价很大（一次无效 IO）

### 2.3 负查占比：Bloom 值不值，先看这个

如果你的 workload 存在：

- cache 穿透（不存在 key 的查询很多）
- 探测式读、过期 key、或上层业务的“先试试有没有”

Bloom 往往非常值钱。反之负查占比很低时，收益会更依赖整体读路径与 cache 情况。

## 3. Ribbon filter（概念层理解即可）

不同 filter 结构在空间/构建/查询上有不同权衡；工程上你可以先抓住不变的部分：

- 目标仍是降低负查的“白跑成本”
- 关注空间占用、构建开销、以及对读路径的实际收益

## 4. 怎么验证 Bloom 是否真的在帮你（闭环）

建议用“负查 → 白跑 IO”做闭环，而不是只看总体读延迟：

1. **统计负查占比**：业务侧/埋点统计不存在 key 的比例
2. **看 filter 命中是否有效**：负查时能否快速排除大部分 SST
3. **看白跑 IO 是否下降**：cache miss 下的无效读盘是否减少

## 5. 常见坑：为什么我开了 Bloom 还是慢

1. **负查占比不高**：收益自然有限
2. **cache miss 太多**：假阳性会更贵；甚至 filter 自己也不够热
3. **结构性读放大太大**：文件数/层级太多，filter 也在为“查太多文件”付费
4. **写入高峰期波动**：flush/compaction 重建与欠账会让读路径抖动

## 6. 最小排障顺序

1. **先看负查占比**：不存在 key 的比例是多少？
2. **看 filter 是否“在内存里且有效”**：能否把 SST 直接排除？
3. **看 cache**：block cache/page cache 是否让假阳性代价变小？
4. **最后看结构性读放大**：文件数、层级、compaction backlog 是否在拖累读路径？
