---
layout: single
title: "对象存储笔记：版本化（versioning）：覆盖写与回收策略"
series: object_storage
categories: [storage]
tags: [存储, 对象存储]
permalink: /object-storage-note-031-versioning/
---
对象存储的 versioning 解决的不是“好不好用”，而是两个非常工程化的问题：

- **防误删/防覆盖**：你永远能找回旧版本（合规/审计/误操作恢复）
- **定义删除语义**：DELETE 的可见性与回收策略要明确（不然会“删了又出现/删了还计费”）

![对象存储 Versioning：覆盖写、delete-marker 与回收](/images/diagrams/object-storage-versioning-flow.svg)

## 1. 开启 versioning 后，覆盖写发生了什么

把它理解成两步：

1. **写入新版本**（生成 `versionId`）
2. **更新“当前指针”**（current version 指向最新版本）

所以 PUT 覆盖写不再是“原地改”，而是“追加一个版本 + 更新指针”。

## 2. DELETE 的语义（常见实现）

很多对象存储在开启 versioning 后，DELETE 的典型行为是：

- 写入一个 **delete-marker**，让“当前指针”变为空（读默认返回 404/NotFound）
- 旧版本仍然存在，并且可以通过 `versionId` 访问（直到生命周期/GC 清理）

这能同时满足“对外看起来删了”与“审计/找回”的需求。

## 3. 回收策略：成本如何被控制住

版本化一定会带来成本问题：旧版本越多，占用越大。

常见控制方式：

- **生命周期策略（lifecycle）**：保留最近 N 个版本 / 超过 X 天自动过期 / 只保留特定 prefix
- **后台 GC/碎片整理**：异步清理旧版本、回收元数据与数据块

关键点：**删除可见 ≠ 成本立刻下降**，成本下降依赖异步回收。

## 4. 排查清单（落地）

1. **版本增长率**：单位时间产生多少新版本？（覆盖写比例）
2. **delete-marker 数量**：是否大量堆积导致 list/元数据变慢？
3. **生命周期/GC backlog**：回收是否跟上？（否则“越用越贵/越慢”）
4. **一致性体验**：list 的一致性窗口是否符合业务预期？（不同系统不同）

## 5. 小结

versioning 的核心是：把“覆盖写/删除”变成可审计、可回滚的版本历史；代价是存储与元数据规模增长，需要 lifecycle + GC 把成本管住。

