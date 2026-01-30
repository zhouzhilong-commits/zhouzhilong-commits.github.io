---
layout: single
title: "Silo：High Performance OLTP（论文笔记）"
series: paper_databases
permalink: /paper-notes/databases/silo-oltp/
---

> 论文：Silo: Exploiting Message Passing and Shared Memory for OLTP（常被用来理解现代高性能 OLTP 的实现要点）

## 1. 这篇论文的核心观点

在多核时代，传统“锁很多 + 共享数据结构争用大”的 OLTP 实现会被瓶颈卡死。
Silo 的核心是把高并发下的关键路径做得更“无锁/低争用”。

## 2. 两个抓手（直觉版）

- **乐观并发控制（OCC）**：先执行，提交时验证冲突
- **版本号/时间戳思路**：用版本来判断读写是否冲突

（不同实现细节很多，但你读 Silo 的第一遍不必被细节淹没，先抓住“提交阶段验证”的主线）

## 3. 为什么它经典

Silo 是很多现代引擎/研究的 baseline：

- 体现“把争用挪到更可控的地方”的设计思想
- 很适合对比：2PL、MVCC、OCC 的不同权衡

## 4. 读完后的 takeaways

OLTP 的关键常常不是算法，而是：

- 数据结构是否有热点争用
- cache line / NUMA 友好性
- 提交路径是否可并行

