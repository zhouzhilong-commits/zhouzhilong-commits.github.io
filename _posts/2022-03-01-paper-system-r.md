---
layout: single
title: "System R：Access Path Selection（论文笔记）"
series: paper_databases
permalink: /paper-notes/databases/system-r-access-path-selection/
---

> 论文：Access Path Selection in a Relational Database Management System（System R）

## 1. 这篇论文解决什么

把 SQL 查询“翻译成一个高质量执行计划”，核心是 **基于代价的优化器（CBO）**：

- 有很多 join 顺序 / access path 可以选
- 需要一个成本模型去估计代价并做搜索

## 2. 两个关键思想

- **动态规划（DP）枚举 join 顺序**：从小集合逐步扩展到大集合
- **Selinger-style cost model**：用统计信息估计基数、IO、CPU 等

## 3. 为什么它经典

你今天看到的大多数关系型数据库优化器，都能看到 System R 的影子：

- 统计信息（histogram/ndv）
- join reordering
- access path（index scan / table scan）

## 4. 读完后的 takeaways

- 优化器的“正确性”很难，但“好用”更难：统计信息质量决定上限
- CBO 的工程化核心是：可维护的成本模型 + 可控的搜索空间

