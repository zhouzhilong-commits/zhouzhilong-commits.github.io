---
layout: single
title: "ARIES：Recovery Algorithm（论文笔记）"
series: paper_databases
permalink: /paper-notes/databases/aries-recovery/
---

> 论文：ARIES: A Transaction Recovery Method Supporting Fine-Granularity Locking and Partial Rollbacks

## 1. ARIES 解决什么

数据库崩溃恢复要同时满足：

- **已提交不丢**（durability）
- **未提交不“半写”**（atomicity）
- 支持并发控制、细粒度锁、甚至部分回滚

## 2. 三个关键词

- **WAL（Write-Ahead Logging）**：先写日志再落数据页
- **LSN**：日志序号，贯穿页与日志记录的关联
- **redo/undo 分离**：能在 crash 后精确重做与撤销

## 3. 恢复三阶段（直觉版）

- **Analysis**：重建事务表/脏页表（知道“可能需要做什么”）
- **Redo**：从某个点开始重放，把系统推进到崩溃前的状态
- **Undo**：撤销未提交事务（用补偿日志 CLR）

## 4. 为什么它经典

很多现代存储引擎（或其变体）都在用类似思想：

- 页级 LSN
- redo/undo
- fuzzy checkpoint

## 5. 读完后的 takeaways

恢复设计的核心不是“能恢复”，而是 **恢复时间、日志量、实现复杂度** 的平衡。

