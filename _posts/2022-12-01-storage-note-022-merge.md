---
layout: single
title: "存储笔记：写入合并（merge）与写扩散：从日志到段"
series: storage_basics
categories: [storage]
tags: [存储, 存储基础系列]
permalink: /storage-note-022-merge/
redirect_from:
  - /storage-note-050-merge/
  - /storage-note-078-merge/
---

本文围绕「存储笔记：写入合并（merge）与写扩散：从日志到段」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![存储笔记：写入合并（merge）与写扩散：从日志到段](/images/diagrams/storage-write-merge-log-to-segment.svg)
## 1. 写入合并的目标

把随机写“聚合”为顺序写：从日志到段/从 memtable 到 SST，本质是用后台重写换取前台吞吐与稳定。

## 2. 代价与副作用

- 写放大（后台合并重写）
- 空间放大（多版本并存、tombstone）

## 3. 排障顺序

先看后台欠账（compaction/merge backlog），再看写入形态（覆盖写/小写），最后调预算与策略。
