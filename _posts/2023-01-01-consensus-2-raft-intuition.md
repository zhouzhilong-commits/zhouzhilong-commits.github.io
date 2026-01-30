---
layout: single
title: "一致性（2）：Raft 直觉（日志复制与提交）"
series: consensus
tags: [分布式一致性]
---

这篇用“直觉模型”理解 Raft：你不需要先记住所有 RPC 和状态机细节，只需要把 **日志（log）** 和 **提交（commit）** 两个核心概念抓牢。

## 1. Raft 在解决什么问题

在一个有副本的系统里，你希望：

- 大多数时候只有一个 leader 负责写入（避免冲突）
- leader 把写入按顺序复制到 followers
- **对外宣称“写成功”** 必须满足一个安全条件（不被回滚）

## 2. 日志复制：把写入变成“追加日志”

你可以把每次写入看成一条日志 entry：

- leader 接受写入，追加到本地日志
- leader 把 entry 复制给 follower（AppendEntries）
- follower 追加成功后返回确认

## 3. 提交：什么时候对外可见

关键点是“commit index”：

- leader 只有在确认某条日志 entry 被复制到 **多数派** 后，才推进 commit index
- 一旦推进，leader 才能对外返回成功，并把该 entry 应用到状态机

这就是为什么多数派能提供安全性直觉：只要多数派里有一台存活，新 leader 选举时不会丢掉已提交日志。

## 4. 你可以如何把它落到工程上

当你在读一个系统的“复制一致性”实现时，可以优先问：

- 写入是不是先变成日志？
- commit 条件是什么（多数派？同步备机？）
- crash/restart 时如何恢复 commit index？

把这 3 个问题想清楚，基本就能读懂大部分基于 Raft 的系统实现。

