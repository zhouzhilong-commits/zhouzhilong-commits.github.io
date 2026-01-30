---
layout: single
title: "存储基础（3）：LSM、Compaction 与写放大"
series: storage_basics
tags: [存储基础系列]
---

这篇是「存储基础系列」的第 3 篇，建立一个 LSM 的“直觉模型”，并解释 compaction 为什么既是性能来源，也是写放大的主要来源。

## 1. LSM 是什么（用一句话）

LSM（Log-Structured Merge-Tree）核心思路：

- **写入先顺序写**（落在内存/日志里，最终顺序写成 SST 文件）
- **后台再把多个有序文件合并**（compaction），维持读性能与空间回收

它特别适合“写多读少 / 随机写多”的场景，因为随机写变成顺序写。

![LSM 层级与 Compaction：数据随着层级下沉会被多次重写](/images/diagrams/lsm-levels-compaction.svg)

## 2. SST、Level、Compaction：三件套

一个典型实现会有：

- **memtable**：内存中的有序结构（跳表/红黑树等）
- **WAL**：写前日志（保证崩溃恢复）
- **SST（Sorted String Table）**：磁盘上的有序文件
- **Levels**：多层文件组织，每层有自己的大小上限
- **Compaction**：把“上层的小文件”合并进“下层的大文件”

### 2.1 L0 为什么经常是“抖动之源”

很多 LSM 实现里，L0 的特点是：**文件之间允许重叠**。这带来两个直接后果：

- **读放大更敏感**：一次点查可能需要查多个 L0 文件（尤其在写高峰、flush 很频繁时）。
- **写停顿更常见**：当 L0 文件数/大小超过阈值，系统通常会触发 stall/throttle，逼迫后台 compaction 追账。

所以线上常见的“写入突然变慢/读突然变慢”，第一反应就是：看看 L0 是否堆积。

## 3. 写放大从哪来

写放大（Write Amplification）可以粗略理解为：

> 应用写入 1 byte，系统实际写入了 N byte

主要来源：

- **Compaction 重写数据**：同一条记录会在多个层级反复被合并、重写。
- **删除与覆盖**：tombstone/旧版本需要通过 compaction 才能真正回收。
- **校验、索引、元数据**：除了 data，本身还有 index/filter 等结构写入。

### 3.1 Leveled vs Tiered：写放大、读放大、空间放大的三角

LSM 里最关键的策略分歧之一是“合并的积极程度”：

- **Leveled**：每层 key-range（尽量）不重叠，读路径更可控，但会更频繁地把上层数据合并进下层 → **WA 往往更高**。
- **Tiered / Universal**：更像“攒一批再合并”，同一条数据被重写次数更少 → **WA 往往更低**，但读要合并更多 run，且空间/版本更难控。

工程上通常不是非黑即白：很多系统会对不同层采用不同策略（例如 L0 特殊处理，底层更“稳”）。

![Leveled vs Tiered：权衡的核心](/images/diagrams/lsm-leveled-vs-tiered.svg)

一个很直觉的结论：

- **层级越深、合并越频繁，写放大越大**
- 但如果层级不深或不合并，**读放大**就会上升

这就是 LSM 的经典权衡：读放大 vs 写放大 vs 空间放大。

## 4. Compaction 为什么会让系统“抖”

你可能见过这类现象：

- 平时写入很稳
- 一到 compaction 高峰，写延迟突然抬头、抖动明显

原因通常是资源竞争：

- **IO 竞争**：compaction 读写吞吐吃掉了磁盘带宽
- **CPU 竞争**：压缩/解压、校验、排序合并消耗 CPU
- **内存压力**：compaction buffer、block cache、memtable 之间互相挤占

### 4.1 你会在监控里看到哪些“前兆”

这类问题最怕“等到写延迟爆炸才发现”。更有效的是盯前兆：

- **L0 文件数/大小** 持续上升
- **pending compaction bytes** 持续上升
- **write stall / throttle** 次数上升
- **读延迟** 同步上升（读要查更多层/更多文件）

### 4.2 Compaction 的本质：把“历史债务”摊到现在

写入时你享受了顺序写（WAL+MemTable+Flush）的红利，但 compaction 会在后台把“多版本、重叠文件、删除标记”清理掉。

因此 compaction 更像“还债”：

- 欠债少：系统稳
- 欠债多：迟早要还（要么后台抢资源导致抖动，要么前台 stall 被迫降速）

## 5. 一个“不会错”的调优方向

不讨论具体系统参数，给一个通用的方向：

- **把 compaction 的 IO/CPU 预算做成可控的“后台配额”**
- **把用户写入的尾延迟保护起来**

对应的工程手段通常是：

- 限制 compaction 并发（线程数/IO）
- 分层/分速率的 compaction 策略（不同层不同优先级）
- 写入节流（当 compaction backlog 过大时保护系统稳定）

### 5.1 正确姿势：把后台资源当成预算

建议把 compaction 当成“后台作业系统”：

- 给它明确的 **IO/CPU 预算**（并发、速率、优先级）
- 给前台写入明确的 **尾延迟保护策略**（stall/throttle 阈值）

这样系统在高峰期会更“可解释”，而不是靠运气。

---

下一篇我们会把“崩溃恢复”补齐：WAL、checkpoint、以及为什么很多系统读写路径都绕不开日志。

