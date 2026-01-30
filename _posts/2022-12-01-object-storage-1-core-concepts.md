---
layout: single
title: "对象存储（1）：对象存储的核心概念（Bucket/Object/Metadata）"
series: object_storage
tags: [对象存储]
---

这篇是对象存储系列的第 1 篇，先把对象存储最核心的抽象讲清楚：**Bucket、Object、Metadata**。

## 1. 对象存储和文件系统/块存储的区别

你可以用一句话区分三者：

- **块存储**：提供块设备（你自己建文件系统/数据库）
- **文件系统**：提供目录树 + POSIX 语义（rename、fsync、权限等）
- **对象存储**：提供“对象（Object）”的读写接口，通常是 HTTP API

对象存储通常不强调 POSIX 语义，而强调：

- 大规模扩展（容量、吞吐）
- 简单 API（PUT/GET/DELETE）
- 持久性与成本优势

## 2. Bucket / Object 是什么

- **Bucket**：逻辑容器（类似“命名空间”），通常用于：
  - 访问控制（权限）
  - 生命周期策略（Lifecycle）
  - 计费与统计维度
- **Object**：真正存储的数据单元，由：
  - key（对象名）
  - data（内容）
  - metadata（元数据）
  组成

## 3. Metadata 为什么重要

对象存储系统里 metadata 常常是“性能与一致性的核心”：

- 你需要快速回答：对象是否存在？大小是多少？etag/version 是什么？
- 你需要保证：PUT/DELETE/overwrite 后 metadata 的可见性与版本关系

因此很多系统都会把 metadata 放在：

- 专用的元数据服务（KV/DB）
- 或者对象存储内部的元数据层

## 4. 一个最小读写路径

以最常见的 GET/PUT 为例：

- PUT：
  - 写 data 到后端存储（分片/纠删码/副本）
  - 写 metadata 并提交版本
- GET：
  - 读 metadata（确认版本、位置、权限等）
  - 读 data（聚合分片/解码）

下一篇我们会讨论“纠删码 vs 副本”：它们分别对成本、性能、修复带来什么影响。

