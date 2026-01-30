---
layout: single
title: "LSM-Tree：The Log-Structured Merge-Tree（论文笔记）"
series: paper_storage
permalink: /paper-notes/storage/lsm-tree/
---

> 论文：The Log-Structured Merge-Tree（O'Neil et al.）

## 1. 论文要点：写优化（write-optimized）

LSM 的核心出发点：

- B+Tree 在随机写场景下会产生大量随机 IO（或随机写放大）
- 如果把写入先变成顺序写，再后台合并，就能显著提高写吞吐

因此它属于典型的 **写优化数据结构**。

## 2. 结构直觉：C0 / C1 / C2…

论文里的经典描述是多级组件：

- **C0**：内存组件（有序结构）
- **C1、C2…**：磁盘组件（分层有序文件）
- 写入先到 C0，后续按一定策略 merge 到更低层

你可以把它理解成“分层的有序 run”，后台持续做归并。

## 3. 代价：读放大、写放大、空间放大

LSM 的收益是写吞吐；代价是三种放大：

- **读放大（RA）**：查询可能要触碰多个层级/文件
- **写放大（WA）**：后台合并会重写数据
- **空间放大（SA）**：多层共存、旧版本与 tombstone 直到合并后才回收

现代系统（LevelDB/RocksDB 等）围绕这三者做了大量工程优化（Bloom filter、cache、compaction 策略等）。

## 4. 读完后的 takeaways

- 一旦工作负载是“写多 + 随机写多”，LSM 家族往往是自然选择
- 真正的难点在 compaction：它决定了系统的稳定性与成本

