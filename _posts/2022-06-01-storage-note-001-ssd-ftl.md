---
layout: single
title: "存储笔记：SSD 写放大与 FTL：为什么随机写更贵"
series: storage_basics
categories: [storage]
tags: [存储, 存储基础系列]
permalink: /storage-note-001-ssd-ftl/
redirect_from:
  - /storage-note-029-ssd-ftl/
  - /storage-note-057-ssd-ftl/
---
你在 SSD 上看到的“写放大”，常常不是上层存储引擎（LSM/B+Tree）带来的那一个，而是**设备内部**也在发生：

- 你写的是 4KB 随机写
- SSD 可能在内部做了更多的搬运/合并/擦除

结果就是：**你在主机侧看到的写入字节 < 盘内实际写入字节**，SSD 的寿命和尾延迟会更敏感。

![SSD / FTL：映射、GC 与设备写放大](/images/diagrams/ssd-ftl-mapping-gc-wa.svg)

## 1. 最小知识：FTL 解决的是什么问题

NAND Flash 的基本限制：

- **不能原地覆盖写**：写过的页（page）不能直接改，需要先擦除所在块（erase block）。
- **擦除粒度更大**：通常 page 是 4KB~16KB，block 可能是几 MB 级别（由 SSD 设计决定）。

因此 SSD 需要一个“地址翻译层”：

- **FTL（Flash Translation Layer）**：把主机看到的 LBA（逻辑块地址）映射到 NAND 的物理页地址（PPA）。

## 2. 为什么随机写更贵：写入不是“覆盖”，而是“追加 + 回收”

把一次覆盖写想成两个阶段：

1. **追加写**：新数据写到一块新的空闲页上（顺序写更友好）。
2. **回收旧页**：旧数据所在页变成“无效页”，等 GC（垃圾回收）把整块搬迁/擦除后才能真正回收空间。

随机写贵，往往是因为：

- 覆盖的 LBA 分散 → 旧页分散在很多 block 里
- GC 回收时不得不“搬运”更多仍然有效的数据
- 搬运越多 → **设备写放大（Device WA）** 越高 → 尾延迟更抖、寿命更短

## 3. 两种写放大：主机侧 vs 设备侧

工程上建议把 “WA” 明确分成两类：

- **Host WA（主机写放大）**：上层引擎带来的额外写入（WAL/compaction/rewrite...）。
- **Device WA（设备写放大）**：SSD 内部搬运/合并/擦除带来的额外写入。

你优化 compaction 把 Host WA 降下来，但如果写入模式导致 Device WA 飙升，系统仍然会抖。

## 4. 你能观测到什么（以及怎么判断是 FTL/GC 在作祟）

常见现象：

- **写入 P99/P999 抖动**：看起来“偶发很慢”，并且和业务流量峰值不完全同步。
- **写入带宽不稳定**：平均 OK，但出现周期性“掉速”。
- **盘寿命/写入量异常**：同样业务写入，某些盘磨损更快（取决于写入分布与 over-provisioning）。

你可以做的验证：

- **对比不同写入模式**：顺序 append vs 随机 overwrite；如果 overwrite 更抖，FTL/GC 影响通常更明显。
- **观察 IO 延迟分布**：是否存在“长尾”且呈现周期性。
- **看设备侧指标**（如果平台提供）：media wear、nand writes、gc activity 等。

## 5. 工程建议：怎么让 SSD 更舒服

- **尽量追加写（append）而不是覆盖写（overwrite）**：日志结构/LSM 的一个重要优势就是更像顺序写。
- **把随机写“聚合”成顺序写**：批量化、对齐、写合并（注意别把 tail latency 搞坏）。
- **给 SSD 留空间（over-provisioning）**：可用空间越逼近满盘，GC 越痛苦。
- **避免长期 95%+ 容量运行**：很多系统在接近满盘时会出现明显抖动与 WA 上升。

## 6. 最小排障清单（遇到 SSD 写入抖动时）

1. **确认是否“接近满盘”**：容量逼近阈值时，GC 代价会非线性上升。
2. **确认是否“随机覆盖写”占比高**：尤其是 4KB 随机 overwrite。
3. **区分 Host WA / Device WA**：不要把所有写放大都怪到 compaction 上。
4. **做 A/B 实验**：相同硬件上，改变写入模式最容易验证 FTL/GC 的影响。

## 7. 小结

SSD 上的性能与寿命，很多时候是“写入形态学”问题：**你写的模式决定了 FTL/GC 的痛苦程度**。把问题拆成 Host vs Device 两段，排障会快很多。

