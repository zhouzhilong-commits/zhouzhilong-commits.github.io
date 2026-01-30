---
layout: single
title: "Spanner：Globally-Distributed Database（论文笔记）"
series: paper_distributed
permalink: /paper-notes/distributed/spanner/
---

> 论文：Spanner: Google's Globally-Distributed Database

## 1. Spanner 解决什么

目标是在全球范围内提供：

- 分布式事务
- 外部一致性（接近线性一致的语义）
- 可扩展与高可用

## 2. TrueTime：这篇论文最著名的点

Spanner 引入 TrueTime（TT）来把“不确定的物理时间”建模成一个区间：

- TT.now() 返回 \([earliest, latest]\)
- 系统通过等待（commit wait）跨过不确定性窗口来保证全局顺序

你可以把它理解为：用工程化时钟同步 + 明确的不确定性边界，来换取更强的一致性语义。

## 3. 数据模型与复制（高层直觉）

- 数据按 key range 分片
- 每个分片由复制组维护（需要一致性协议保证写入）
- 事务通过两阶段提交等机制协调多个分片

## 4. 为什么它经典

Spanner 把“全球一致的事务数据库”从理论走到工程落地：

- 明确地展示了时间、不确定性与一致性的关系
- 给出了很多系统设计的工程答案（复制、分片、事务、时钟）

## 5. 读完后的 takeaways

强一致不是“免费”的：你要付出延迟（等待）、实现复杂度与基础设施成本（时间同步）。

