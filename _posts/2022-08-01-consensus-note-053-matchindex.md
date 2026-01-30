---
layout: single
title: "一致性笔记：日志复制：matchIndex 与提交规则"
series: consensus
categories: [distributed]
tags: [分布式, 一致性]
permalink: /consensus-note-053-matchindex/
---

本文围绕「一致性笔记：日志复制：matchIndex 与提交规则」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。

![一致性笔记：日志复制：matchIndex 与提交规则](/images/diagrams/raft-matchindex-commit.svg)
## 1. 两个 index 的直觉：一个看“复制进度”，一个看“对外承诺”

- **matchIndex（per follower）**：leader 认为该 follower 已经复制到的最高日志 index。
- **commitIndex（leader 维护）**：已经被“多数派确认”的最高日志 index，可以对外承诺（可被状态机应用）。

一句话：matchIndex 是“每个副本跟到哪”，commitIndex 是“系统能承诺到哪”。

## 2. 为什么提交规则要看多数派：安全性来自交集

当一个日志条目在多数派上复制完成，后续任何多数派一定有交集能“看到它”，因此它不会被未来的 leader 丢掉（在经典 Raft 语义下）。

这也是为什么：

- 写入延迟经常被 **quorum 路径** 的尾延迟主导
- 慢副本如果经常落入多数派路径，会放大 P99

## 3. 线上最常见的现象：慢副本如何制造长尾

你可能会看到：

- **commitIndex 推进变慢**：写入等待多数派复制完成。
- **复制 backlog 变大**：某些 follower 的 matchIndex 长期落后。
- **选主抖动**：复制慢 + 心跳超时，可能触发频繁选主（取决于实现与超时参数）。

慢副本常见根因：

- 网络 RTT/丢包/重传（尾部抖动）
- follower 磁盘抖动（fsync、队列化）
- follower CPU/GC 抢占（压缩、后台任务、邻居噪声）

## 4. 你应该观测什么（从最有用的开始）

- **per-follower matchIndex/backlog**：谁在拖后腿？拖了多久？
- **append/replicate 延迟分布**：复制链路 P99 是否异常？
- **leader commit latency**：写入从提交到应用的端到端延迟（如果能打点）
- **选主频率与原因**：是否因心跳超时误判？

## 5. 最小排障顺序

1. **先定位慢副本**：按 follower 排序看 matchIndex/backlog（谁最慢，最重要）。
2. **再定位慢在哪一段**：网络（RTT/重传）还是磁盘（fsync/队列）还是 CPU（抢占/GC）。
3. **看副本布局与多数派路径**：是否经常把慢副本纳入多数派确认路径（跨域/跨 AZ 设计是否合理）。
4. **最后才谈限速与参数**：在定位根因前调超时/窗口，往往只会把问题“挪走”。

## 6. 小结

matchIndex 让你看到“每个副本欠账多少”，commitIndex 决定“系统能承诺多少”。线上长尾优化的抓手通常就是：**找出拖慢多数派确认的那条最慢链路**，把它从“多数派路径”里移走或把它治好。
