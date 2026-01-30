---
layout: single
title: "计算机组成笔记：Profile 指标：IPC、cache miss、branch miss"
series: cs_arch
categories: [cs]
tags: [计算机基础, 计算机组成]
permalink: /cs-arch-note-070-profile-ipc-cache-miss-branch-miss/
---
这篇讲一套最常用、也最容易落地的“性能诊断直觉”：当你看到 **IPC 低**，不要先怀疑“CPU 太慢”，而是先问一句：**流水线在等什么？**

![Profile 指标：IPC/caches/branch 的直觉关系](/images/diagrams/profile-metrics-ipc-cache-branch.svg)

## 1. IPC 是什么，为什么它很有用

IPC（Instructions Per Cycle）≈ 每个周期退休多少条指令。它不是“越高越好”的 KPI，但它能快速告诉你：

- 你的程序是在 **算（compute-bound）**，还是在 **等（stall-bound）**

## 2. cache miss 与 IPC：最常见的“等”

当 L1/L2/LLC miss 上升时，CPU 需要去更慢的层级取数据：

- L1 miss → 可能去 L2
- L2 miss → 可能去 LLC
- LLC miss → 可能去 DRAM（最贵）

表现出来通常是：**stalled cycles 上升，IPC 下降**。

## 3. branch miss 与 IPC：另一种“等”

分支预测失败会导致流水线 flush：之前投机执行的工作作废。

表现通常是：

- branch-misses 上升
- IPC 下降（但不一定伴随大量 cache miss）

## 4. 排查清单（建议照顺序）

1. **先判定类型**：stalled cycles 是否很高？（先判定“等”为主还是“算”为主）
2. **再看 cache**：L1/L2/LLC miss 哪个高？是否有明显的热点数据结构/访问模式？
3. **再看分支**：branch miss 是否异常？是否有大量不可预测分支（hash/状态机）？
4. **落到函数**：用 `perf record`/火焰图定位热点函数，再回到数据结构/算法改造

## 5. 小结

IPC 低通常不是结论，而是“提示你去看 stall 的来源”。把 stalled cycles + cache miss + branch miss 结合起来，你就能把性能问题从“感觉慢”变成“知道在等什么”。

