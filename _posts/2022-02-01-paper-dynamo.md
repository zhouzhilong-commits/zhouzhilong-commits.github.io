---
layout: single
title: "Dynamo：Amazon's Highly Available Key-value Store（论文笔记）"
series: paper_storage
permalink: /paper-notes/storage/dynamo/
---

> 论文：Dynamo: Amazon's Highly Available Key-value Store（DeCandia et al.）

## 1. Dynamo 解决什么问题

Dynamo 的核心目标是 **高可用**（availability）：

- 面向电商业务：购物车、会话等
- 更看重“服务不断”而不是强一致

因此它的设计选择是：在 CAP 取舍中明显偏向 **A**（以及分区容忍 P）。

## 2. 核心机制一览

论文里最经典的一组组合拳：

- **一致性哈希（consistent hashing）**：做分片与节点扩缩容
- **多副本**：提高容错
- **Quorum 读写（R/W/N）**：用多数派交集提高一致性概率
- **Vector clock**：解决并发写的版本冲突（保留多个版本，由应用合并）
- **Hinted handoff / Read repair**：在故障与恢复中修复副本一致性

## 3. “最终一致”到底意味着什么

Dynamo 的关键点不是“放弃一致性”，而是把一致性问题显式化：

- 系统允许短时间内不一致
- 冲突会以多版本形式暴露给上层（vector clock）
- 上层用业务逻辑做合并（例如购物车合并）

## 4. 读完后的 takeaways

- 很多分布式系统的实用技巧，Dynamo 都给出了工程化范式
- 不同业务对一致性/可用性的要求不同，系统设计必须服务业务目标

