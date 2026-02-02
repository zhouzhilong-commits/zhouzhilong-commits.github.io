---
layout: single
title: "KV存储笔记：Compaction 策略与写放大"
series: kv_storage
categories: [storage]
tags: [存储, kv存储]
date: 2021-06-25
permalink: /kv-storage-note-002-compaction/
---

## 前言

Compaction 是 LSM-Tree 存储引擎的核心操作，负责合并多个 SSTable 文件，减少文件数量并回收空间。本文从 KV 存储系统的实际实现角度，介绍 Compaction 在 KV 存储中的策略选择、写放大控制、性能优化以及实际应用案例。

> 注：本文聚焦于 KV 存储系统中 Compaction 的具体实现。关于 LSM-Tree 和 Compaction 的通用原理，请参考「存储基础系列」的相关文章。

## 1. Compaction 的目的

Compaction 的主要目的：

1. **减少文件数量**：合并多个小文件为一个大文件
2. **回收空间**：删除已覆盖或已删除的数据
3. **优化读取**：减少查询时需要访问的文件数量
4. **控制层级**：维护 LSM-Tree 的层级结构

## 2. Compaction 策略

### 2.1 Leveled Compaction

将数据组织成多个层级，每个层级有固定的大小限制：

- **L0**：MemTable 刷盘后的文件，可能有重叠
- **L1-Ln**：每层文件大小递增，且同一层内文件不重叠
- **Compaction**：将上层文件合并到下层

**优点**：
- 读取性能稳定
- 空间放大可控

**缺点**：
- 写放大较大
- Compaction 开销高

### 2.2 Size-Tiered Compaction

将大小相近的文件合并：

- 当同层文件数量达到阈值时触发合并
- 合并后的文件大小翻倍
- 继续合并直到达到最大文件大小

**优点**：
- 写放大相对较小
- 实现简单

**缺点**：
- 读取可能需要访问多个文件
- 空间放大较大

### 2.3 Tiered + Leveled 混合策略

结合两种策略的优点：

- 上层使用 Size-Tiered
- 下层使用 Leveled
- 平衡写放大和读性能

## 3. 写放大问题

### 3.1 写放大的来源

写放大（Write Amplification）是指实际写入磁盘的数据量大于用户写入的数据量：

- **重复写入**：数据在 Compaction 过程中被多次写入
- **索引更新**：需要更新索引结构
- **元数据写入**：需要写入文件元数据

### 3.2 写放大的计算

```
写放大 = 实际写入磁盘的数据量 / 用户写入的数据量
```

### 3.3 如何减少写放大

1. **调整 Compaction 策略**：选择写放大较小的策略
2. **增加层级大小**：减少 Compaction 频率
3. **批量 Compaction**：合并多个小 Compaction 为一个大 Compaction
4. **延迟 Compaction**：在低峰期执行 Compaction

## 4. Compaction 的触发条件

### 4.1 基于文件数量

- 当某一层的文件数量达到阈值时触发
- 简单直接，易于实现

### 4.2 基于文件大小

- 当文件总大小达到阈值时触发
- 可以更好地控制空间使用

### 4.3 基于时间

- 定期执行 Compaction
- 保证数据及时整理

### 4.4 基于读取放大

- 监控读取需要访问的文件数量
- 当读取放大过大时触发 Compaction

## 5. Compaction 的性能优化

### 5.1 并行 Compaction

- 多个 Compaction 任务并行执行
- 充分利用多核 CPU 和磁盘 IO

### 5.2 增量 Compaction

- 只合并变化的部分
- 减少 Compaction 的数据量

### 5.3 优先级调度

- 优先 Compaction 热点数据
- 延迟 Compaction 冷数据

### 5.4 IO 限流

- 控制 Compaction 的 IO 速率
- 避免影响正常读写操作

## 6. Compaction 与查询性能

### 6.1 文件数量对查询的影响

- 文件数量越多，查询需要访问的文件越多
- Compaction 可以减少文件数量，提高查询性能

### 6.2 Bloom Filter 的作用

- 每个 SSTable 可以配备 Bloom Filter
- 快速判断键是否存在于文件中
- 减少不必要的文件访问

## 7. KV 存储系统中的 Compaction 实现案例

### 7.1 RocksDB 的 Compaction 策略

RocksDB 支持多种 Compaction 策略：

- **Leveled Compaction**：默认策略，适合大多数场景
- **Universal Compaction**：适合写多读少的场景
- **FIFO Compaction**：适合时序数据，自动删除最旧的数据
- **Tiered Compaction**：适合写放大敏感的场景

### 7.2 LevelDB 的 Compaction 策略

LevelDB 使用 Leveled Compaction：

- **固定层级大小**：每层大小固定，便于控制
- **自动触发**：当文件数量或大小达到阈值时自动触发
- **优先级调度**：优先 Compaction 上层文件

### 7.3 BadgerDB 的 Compaction 策略

BadgerDB 使用特殊的 Compaction 策略：

- **Value Log Compaction**：专门针对大 Value 的 Compaction
- **LSM Compaction**：针对 Key 的 Compaction
- **分离设计**：Key 和 Value 分别 Compaction

## 8. KV 存储系统中的特殊优化

### 8.1 TTL 数据的 Compaction

KV 存储系统通常支持 TTL（Time To Live），Compaction 需要：

- **过期检测**：在 Compaction 时检测并删除过期数据
- **批量删除**：批量删除过期数据，提高效率
- **时间窗口**：根据时间窗口组织数据，便于批量删除

### 8.2 大 Value 的 Compaction

KV 存储系统的 Value 可能很大，Compaction 需要：

- **Value 分离**：大 Value 存储在单独的文件中
- **增量 Compaction**：只 Compaction 变化的部分
- **流式处理**：支持流式处理大 Value，避免内存占用过大

### 8.3 多版本数据的 Compaction

KV 存储系统可能需要多版本，Compaction 需要：

- **版本合并**：合并多个版本，只保留最新版本
- **版本清理**：清理旧版本，回收空间
- **快照支持**：支持快照，避免清理正在使用的版本

## 9. 性能调优实践

### 9.1 Compaction 参数调优

```cpp
// KV 存储系统的 Compaction 参数配置示例
struct CompactionOptions {
    // Leveled Compaction 参数
    int max_levels = 7;              // 最大层级数
    size_t level0_file_num = 4;      // L0 文件数量阈值
    size_t level0_size = 256 * MB;   // L0 大小阈值
    
    // 写放大控制
    double max_write_amplification = 10.0;  // 最大写放大
    int compaction_priority = 1;            // Compaction 优先级
    
    // 性能优化
    int max_compaction_threads = 4;   // 最大 Compaction 线程数
    size_t compaction_buffer_size = 64 * MB;  // Compaction 缓冲区大小
    bool enable_parallel_compaction = true;   // 启用并行 Compaction
};
```

### 9.2 动态调整策略

```cpp
// KV 存储系统的动态 Compaction 调整
class AdaptiveCompaction {
    void adjust_compaction_strategy() {
        // 根据系统负载动态调整
        if (write_amplification > threshold_) {
            // 写放大过大，减少 Compaction 频率
            increase_compaction_interval();
        }
        
        if (read_amplification > threshold_) {
            // 读放大过大，增加 Compaction 频率
            decrease_compaction_interval();
        }
        
        // 根据 IO 负载调整
        if (io_utilization > threshold_) {
            // IO 负载高，降低 Compaction 优先级
            reduce_compaction_priority();
        }
    }
};
```

## 10. 监控与诊断

### 10.1 关键指标

KV 存储系统需要监控的 Compaction 指标：

- **写放大**：实际写入量 / 用户写入量
- **读放大**：查询需要访问的文件数量
- **空间放大**：实际占用空间 / 逻辑数据大小
- **Compaction 延迟**：Compaction 操作的耗时
- **Compaction 吞吐**：Compaction 的数据量

### 10.2 问题诊断

常见问题及诊断方法：

- **写放大过大**：检查 Compaction 策略，考虑切换到 Tiered
- **读放大过大**：检查文件数量，增加 Compaction 频率
- **Compaction 延迟高**：检查 IO 负载，调整 Compaction 优先级
- **空间放大过大**：检查删除操作，确保 Compaction 及时清理

## 11. 小结

Compaction 是 LSM-Tree 存储引擎的关键操作，需要在写放大、读性能、空间效率之间找到平衡。

**核心要点**：

- **Compaction 的目的**：减少文件数量、回收空间、优化读取、控制层级
- **策略选择**：Leveled、Tiered、混合策略各有优劣
- **写放大控制**：通过调整策略、增加层级大小、批量 Compaction 等方式减少写放大
- **性能优化**：并行 Compaction、增量 Compaction、优先级调度、IO 限流

**在 KV 存储系统中的特殊考虑**：

- **TTL 支持**：需要在 Compaction 时处理过期数据
- **大 Value 处理**：需要特殊设计避免 Compaction 开销过大
- **多版本支持**：需要合并和清理多个版本

选择合适的 Compaction 策略和优化方案，可以显著提升 KV 存储系统的整体性能。不同的 KV 存储系统根据其应用场景，会采用不同的 Compaction 实现策略。
