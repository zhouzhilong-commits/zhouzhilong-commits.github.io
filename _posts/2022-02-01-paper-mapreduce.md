---
layout: single
title: "MapReduce：Simplified Data Processing（论文笔记）"
series: paper_distributed
permalink: /paper-notes/distributed/mapreduce/
---

> 论文：MapReduce: Simplified Data Processing on Large Clusters

## 1. MapReduce 提供什么抽象

把大规模数据处理抽象成两个函数：

- **Map**：把输入拆成一堆 (k, v)
- **Reduce**：按 key 聚合处理

框架负责：

- 分片与调度
- shuffle（按 key 重新分区、传输、排序）
- 容错（失败重试）

## 2. 为什么它经典

它把“分布式系统复杂度”从业务代码里剥离出来，让：

- 业务只写 map/reduce 逻辑
- 系统负责并行、容错与数据流动

后来很多系统都受其影响（Spark、Flink 等在模型上演进）。

## 3. 容错直觉

- 任务是可重试的（deterministic 更好）
- 中间结果可重算/可落盘
- 调度器能在故障机器上重新跑任务

## 4. 读完后的 takeaways

MapReduce 的价值不只是 API，而是完整的“工程闭环”：调度 + 数据流 + 容错。

