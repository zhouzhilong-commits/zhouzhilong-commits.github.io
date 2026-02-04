---
layout: single
title: "操作系统笔记：NUMA：内存分配与远端访问的代价"
series: cs_os
categories: [cs]
tags: [计算机基础, 操作系统, NUMA, 内存, 性能]
date: 2019-09-01
permalink: /cs-os-note-050-numa-memory-allocation/
---

NUMA（Non-Uniform Memory Access）机器上，“同样是内存访问”并不等价：访问本地 NUMA 节点的内存更快，访问远端节点更慢，且会引入额外互连流量。对延迟敏感服务而言，NUMA 问题经常表现为：

- P99/P999 抖动
- 线程迁移后性能突然变化
- 某些核很忙但整体吞吐不高

这篇笔记把 NUMA 相关的三个工程问题串起来：

- **内存分配在哪里发生**（first-touch）
- **线程跑在哪里**（CPU 亲和性）
- **数据被谁访问**（跨节点共享与伪共享）

---

## 1. NUMA 的结构：socket = node，内存就近

简化示意：

```
Socket/Node 0: CPUs (cores) + Local DRAM 0
Socket/Node 1: CPUs (cores) + Local DRAM 1

Remote access:
  CPU0 reads DRAM1 -> via interconnect (slower)
```

代价通常体现为：

- 更高的访问延迟
- 更低的有效带宽
- 更大的互连拥塞风险（多核同时跨节点访问）

---

## 2. first-touch：页在哪里分配，取决于第一次写

很多 Linux 配置下，匿名页（heap 等）采用 first-touch：

- 某线程第一次写入该页时，页被分配在该线程所在 CPU 的 NUMA 节点

这意味着：

- 初始化线程在哪个节点触页，决定后续数据的位置
- 如果初始化在 node0，但主要访问在 node1，就会产生大量远端访问

示意：

```
Thread on node0 initializes array -> pages allocated on node0
Thread on node1 later processes array -> remote accesses
```

工程策略：

- 让“初始化/触页”的线程与“主要使用”的线程在同一节点
- 或按分区初始化：每个 worker 初始化自己会处理的数据分片

---

## 3. CPU 亲和性：线程跑哪决定了访问路径

如果线程频繁跨节点迁移：

- cache/TLB 失效
- 新节点访问旧节点内存 -> remote
-> 延迟与吞吐更不稳定

常见策略：

- 绑定线程到一组核（cpuset/affinity）
- NUMA aware 调度（让线程尽量留在其数据所在节点）

但也要避免过度绑定导致：

- 某节点过载而另一个节点空闲

---

## 4. 跨节点共享：远端访问与一致性流量

当两个节点的核频繁写同一 cache line：

- 发生 cache coherence 流量
- 在 NUMA 下不仅跨核，还跨 socket 互连
-> 代价更大

这类问题常与伪共享相互叠加：

- 数据结构布局不当，多线程写落在同一 cache line
- 即使逻辑上“不同字段”，也会互相拉扯

工程手段：

- padding/对齐，避免多线程写共享同一 line
- 把写热点改为分片计数（per-thread/per-core），最后聚合

---

## 5. 内存策略：interleave、bind 与大页

常见内存策略（抽象）：

- **bind**：把分配限制在某个节点（更可预测，但可能耗尽）
- **preferred**：优先本地，必要时可远端
- **interleave**：在多个节点间交错分配（带宽更均匀，但延迟更平均）

选择取决于负载：

- 延迟敏感：通常 prefer/bind，本地化优先
- 带宽敏感（流式扫描）：interleave 可能更好

大页（THP/hugepage）也会影响：

- 页分配粒度更大，first-touch 影响更显著
- TLB miss 降低，但分配/回收成本可能上升

---

## 6. 观测与排查

建议关注：

- 远端访问比例（local vs remote）
- 节点间互连带宽/拥塞（如果可观测）
- 线程迁移次数、跨节点迁移次数
- 每节点内存分配量与回收压力

典型定位路径：

- P99 抖动 + 远端访问上升：数据不本地或线程漂移
- 吞吐下降 + 互连忙：跨节点共享写热点（coherence 风暴）

---

## 7. 小结

NUMA 的工程本质是“数据与执行的空间一致性”：

- first-touch 决定数据在哪里
- 亲和性决定线程在哪里
- 共享写决定互连与一致性流量

在高并发服务中，NUMA 问题往往不是“平均变慢”，而是“尾延迟变差”。把数据分片、初始化本地化、减少跨节点共享写，是最常用也最有效的稳定性手段。

