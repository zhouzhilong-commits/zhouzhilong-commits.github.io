---
layout: single
title: "组成（1）：CPU Cache 与局部性"
series: cs_arch
permalink: /cs/architecture/cpu-cache-and-locality/
tags: [计算机组成]
---

这篇只讲一件事：**为什么“局部性”几乎决定了性能上限**。

## 1. 为什么需要 Cache

CPU 计算越来越快，但内存访问相对更慢。
Cache 的目标是：把“可能马上要用的数据”放在更快的层级里（L1/L2/L3）。

## 2. 两种局部性

- **时间局部性**：刚用过的数据，短时间内还会再用
- **空间局部性**：访问某个地址后，附近地址很可能也会被访问

这也是为什么顺序扫描通常比随机访问更快。

## 3. 你会在工程里直接感受到的点

- 数据结构设计会影响 cache miss（例如链表 vs 数组）
- 访问模式会影响预取效果（prefetch）
- false sharing 会让多线程性能崩掉（同一 cache line 被不同线程频繁写）

