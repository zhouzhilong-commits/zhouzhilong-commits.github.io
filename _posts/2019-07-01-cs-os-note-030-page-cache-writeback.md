---
layout: single
title: "操作系统笔记：Page Cache 与回写（writeback）：为什么会抖"
series: cs_os
categories: [cs]
tags: [计算机基础, 操作系统, IO, PageCache, writeback]
date: 2019-07-01
permalink: /cs-os-note-030-page-cache-writeback/
---

线上常见的“IO 抖动”现象里，page cache 与 writeback（回写）经常是主角：吞吐看起来没变，但 P99/P999 延迟突然上升，甚至出现周期性尖刺。

这篇笔记把 page cache 当成一个“**缓冲 + 合并 + 延迟写**”系统来看，重点解释：

- 写入为什么看起来很快（写进 cache 就返回）
- 为什么会突然变慢（脏页太多触发回写/节流）
- 回写如何影响前台读写延迟（IO 队列竞争）
- 工程上如何观测与定位（脏页水位、回写速率、direct IO 的取舍）

---

## 1. page cache：把文件 IO 变成内存 IO（大部分时候）

page cache 是内核维护的文件内容缓存（以页为单位）。读写路径可以粗略抽象为：

### 1.1 读

```
read(file, offset, len):
  if pages in page cache:
     memcpy to user buffer
  else:
     schedule disk read -> fill cache -> memcpy
```

### 1.2 写（buffered write）

```
write(file, offset, data):
  copy data into page cache pages
  mark pages dirty
  return (often before disk write completes)
```

写得快的原因：很多写只做了内存拷贝 + 标记脏页。

---

## 2. 脏页（dirty pages）：延迟写带来的“债务”

脏页 = page cache 中被修改但尚未写回磁盘的页面。

脏页带来两个核心风险：

- **持久性窗口**：崩溃会丢最近写（取决于 fsync/写策略）
- **回写压力**：脏页积累到一定程度后必须写回，否则内存会被占满

为了控制风险，内核有一套水位与策略（抽象）：

- background threshold：超过后后台开始回写
- dirty threshold：超过后前台写会被节流（throttle），甚至阻塞等待回写

---

## 3. writeback：后台回写与前台节流

### 3.1 为什么会抖：从“写进 cache”到“等磁盘”

当系统健康时：

- 写入速率 <= 磁盘可持续回写速率
- 脏页水位稳定

当写入突增或磁盘变慢时：

- 脏页上涨
- 达到阈值后触发更激进的回写
- 前台写被节流，延迟上升

```
time ->

dirty pages:
  low/steady  -> rising -> hit threshold -> throttle -> recover

latency:
  low         -> ok     -> spikes (throttle) -> ok
```

### 3.2 回写为何会影响读延迟

回写会占用：

- 磁盘带宽
- IO 队列深度
- 设备内部缓存/调度

如果没有 QoS 隔离，前台读与后台回写会在同一设备队列竞争，读 P99 会抬升。

---

## 4. fsync / fdatasync：把“债务”提前结清

应用调用 fsync 的语义是：要求相关数据与元数据落盘（抽象，具体取决于文件系统）。

工程直觉：

- fsync 频繁：写延迟更高、更稳定（把回写前移到请求路径）
- fsync 很少：写延迟低，但可能周期性抖（债务集中结算）

如果系统依赖 WAL（写前日志）：

- WAL 通常要求 fsync（或等价持久性）保证提交语义
- 数据文件可以更异步（取决于设计）

---

## 5. buffered IO vs direct IO：两条路

### 5.1 buffered IO（默认）

优点：

- 利用 page cache 提高命中率
- 合并小写、顺序化写

缺点：

- 脏页 + writeback 带来不可预测的尾延迟
- 双缓存（应用缓存 + page cache）可能浪费内存

### 5.2 direct IO（绕过 page cache）

优点：

- 延迟更可预测（少了脏页债务）
- 避免双缓存

缺点：

- 应用必须自己做缓存与对齐（复杂）
- 小 IO 性能可能更差（无法利用 cache 合并）

工程常见折中：

- 数据文件 direct IO + 应用缓存
- 日志文件 buffered + 频繁 fsync（或相反，视系统）

---

## 6. 观测指标与排查

### 6.1 脏页与回写指标

建议关注：

- 脏页占比/大小（dirty pages）
- 回写速率（writeback MB/s）
- 节流次数/时长（writeback throttle）
- IO 队列深度、设备 util、平均等待时间

### 6.2 常见诊断路径

现象：写延迟周期性尖刺

排查：

- 看脏页是否周期性冲到阈值
- 看回写速率是否跟不上写入速率
- 看设备是否在某些时段变慢（GC、重映射、共享盘干扰）

现象：读 P99 随写入升高

排查：

- 回写是否占满队列导致读被排队
- 是否需要 IO 优先级/队列隔离

---

## 7. 小结

page cache 把大量 IO 变成“内存操作”，但它引入了一个必然的系统性代价：脏页债务。写入突增或磁盘变慢时，债务会被集中回收，从而表现为 writeback/throttle 造成的尾延迟抖动。工程上，稳定性依赖：

- 脏页水位与回写速率的匹配
- 前台与后台 IO 的隔离能力
- 是否选择 direct IO/应用缓存的架构取舍

