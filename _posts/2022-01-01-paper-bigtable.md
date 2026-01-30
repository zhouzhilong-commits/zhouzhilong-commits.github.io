---
layout: single
title: "Bigtable：A Distributed Storage System for Structured Data（论文笔记）"
series: paper_storage
permalink: /paper-notes/storage/bigtable/
---

> 论文：Bigtable: A Distributed Storage System for Structured Data（Chang et al.）

## 1. Bigtable 提供什么抽象

Bigtable 对外提供的是一个巨大的稀疏表：

- row key（行键）
- column family: qualifier（列族 + 列）
- timestamp（多版本）

你可以把它理解成一个“按 row key 排序”的分布式 KV，只是 value 里又做了 column family 与多版本。

## 2. Tablet：按 row key 分片

Bigtable 以 **tablet** 为基本分片单位：

- tablet 是一个 row key 范围
- tablet 由某个 TabletServer 负责
- tablet 可以拆分/迁移，实现扩展与负载均衡

这使得 Bigtable 的扩展模型非常清晰：增加 TabletServer，迁移/拆分 tablet。

## 3. 依赖：GFS + Chubby

论文里很典型的“Google 三件套”：

- **GFS**：底层持久化存储（SSTable/日志等落在 GFS）
- **Chubby**：分布式锁与少量元数据（选主、tablet 位置等）

这体现了一个重要工程原则：

> 把“强一致的小状态”交给专门的协调服务，把“大数据”交给吞吐型存储。

## 4. SSTable / MemTable：写入与读路径

Bigtable 的核心读写链路和很多 LSM 系统一脉相承：

- 写入先落日志 + MemTable
- MemTable flush 成 SSTable
- 后台 compaction 合并 SSTable

## 5. 读完后的 takeaways

- 抽象很重要：row key 排序 + tablet 分片，让系统扩展与运维都更简单
- “协调小状态 / 数据大状态”分层：是构建大规模系统的常用模式
- Bigtable 的设计后来影响了大量系统（HBase、Cassandra 等）

