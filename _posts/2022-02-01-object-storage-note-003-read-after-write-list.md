---
layout: single
title: "对象存储笔记：一致性模型：read-after-write 与 list 一致性"
series: object_storage
categories: [storage]
tags: [存储, 对象存储]
permalink: /object-storage-note-003-read-after-write-list/
redirect_from:
  - /object-storage-note-052-read-after-write-list/
---
对象存储里最容易踩坑的是一句话：

> **“我写成功了”并不等于 “所有读路径（尤其是 LIST）立刻都能看到”。**

这篇把一致性拆成四类语义（新建/覆盖/删除/列表），并给出工程上最常用的应对方式。

![对象存储一致性：PUT/GET/LIST 的传播链路与“列表滞后”来源](/images/diagrams/object-storage-consistency-put-get-list.svg)

## 1. 先把问题说清楚：你关心的是哪一种一致性

对象存储常见 API：

- `PUT object`：创建/覆盖对象
- `GET object`：读取对象内容
- `DELETE object`：删除（可能是 delete-marker）
- `LIST prefix`：列举某个前缀下的对象集合

一致性语义不是一句 “strong / eventual” 能概括的，至少要区分：

- **新建对象**（key 之前不存在）
- **覆盖对象**（同 key 写新版本）
- **删除对象**
- **列表/目录视图**（LIST/HEAD 的索引视图）

## 2. 一个非常实用的“语义表”（写系统/写业务都够用）

你可以用下面的问题自测你需要什么承诺：

- **Q1：PUT 成功后，立刻 GET，必须读到新内容吗？**
- **Q2：PUT 覆盖旧对象后，立刻 GET，允许读到旧内容吗？允许多久？**
- **Q3：DELETE 后，立刻 GET，允许短暂读到旧内容吗？**
- **Q4：PUT/DELETE 后，立刻 LIST，必须立刻出现在列表里吗？**

> 大多数系统里，**GET 的一致性比 LIST 更容易做强**：GET 只需要命中单 key 的元数据/路由；LIST 往往依赖“前缀索引/目录索引”的异步更新。

## 3. 为什么 LIST 更容易“看不到”：本质是索引传播问题

LIST 背后通常不是“扫全量数据”，而是：

- 维护一个 **prefix → keys** 的目录/索引（为了性能与成本）
- 写入路径先保证对象内容/元数据落盘，然后**异步**更新索引（或跨分区聚合）

于是就出现经典现象：

- PUT 成功后 **GET 能读到**
- 但 **LIST 暂时看不到**

这不是 bug，而是架构选择：用更弱的 LIST 语义换取更可扩展的目录服务。

## 4. 工程上怎么“把语义补回来”（4 种常用打法）

### 4.1 版本化（versioning）+ 条件读（If-Match / If-None-Match）

核心思路：**业务对“哪个版本算成功”有明确标识**，而不是靠 LIST 的“目录视图”判断。

- 写入返回 `versionId/etag`
- 读时带条件：读不到就重试或回退

### 4.2 commit marker / manifest（把“可见性”显式化）

典型做法：

1. 先 PUT 数据对象（可能是分片）
2. 最后 PUT 一个小的 `manifest/commit` 对象作为“完成标志”
3. 读侧只信 commit 对象（而不是信 LIST）

这能把“读到半套数据”的概率降到非常低。

### 4.3 业务侧不要用 LIST 当强一致目录

如果你需要“目录强一致”，建议引入独立的强一致元数据系统（DB/KV）：

- DB 存目录与版本
- 对象存储只放大对象（payload）

这也是很多大型系统的标准拆分：**元数据强一致，数据弱一致**。

### 4.4 对象覆盖写：尽量“写新 key，再切换指针”

覆盖同 key 更容易出现“读旧内容/旧缓存”的问题。常用技巧：

- 写到新 key（带版本/时间戳）
- 更新一个指针/元数据（强一致）
- 旧 key 延后 GC

## 5. 怎么验证/观测：把一致性变成可量化指标

建议定义两个指标（非常实用）：

- **Read-after-write success rate**：PUT 后立刻 GET，成功比例（按时间窗分桶）。
- **List visibility lag**：PUT 后多久能在 LIST 出现（统计分位数）。

再配一套最小实验：

1. 对同一 prefix 连续 PUT 多个对象
2. 每次 PUT 后立刻 GET 校验内容
3. 同时循环 LIST，记录“第一次看到该 key 的时间”

你会很快得到：不同 region、不同负载下，LIST 的滞后分布长什么样。

## 6. 最小排障清单（线上出现“写了但看不到”）

1. **先区分 GET vs LIST**：到底是读不到对象，还是列表看不到？
2. **确认是否覆盖写**：覆盖写比新建更容易出现缓存/旧版本问题。
3. **确认是否跨 region/跨 AZ**：跨域复制会引入天然传播延迟。
4. **不要用 LIST 当强一致目录**：用 commit marker 或强一致元数据系统兜底。

## 7. 小结

对象存储的一致性问题，99% 都能用“把语义说清楚 + 把可见性显式化 + 把 LIST 当成弱一致索引”来解决。真正难的不是实现，而是**业务是否接受明确的语义边界**。

