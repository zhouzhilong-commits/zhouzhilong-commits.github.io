---
layout: single
title: "IndexLib（9）：Locator 与数据一致性"
series: indexlib
permalink: /indexlib-9-locator-consistency/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-07-09
---

在上一篇文章中，我们深入了解了索引类型的实现。本文将继续深入，详细解析 Locator 的实现细节和数据一致性保证机制，这是理解 IndexLib 如何保证数据不重复、不丢失的关键。

![Locator 与数据一致性概览：从 Locator 结构到数据一致性保证的完整机制](/images/diagrams/indexlib-locator-consistency-overview.svg)

## 1. Locator 深入解析

### 1.1 Locator 的完整结构

`Locator` 是增量更新的核心，定义在 `framework/Locator.h` 中：

```cpp
// framework/Locator.h
class Locator final
{
public:
    // Locator 比较结果
    enum class LocatorCompareResult {
        LCR_INVALID,        // 无效
        LCR_SLOWER,         // 比这个 locator 慢
        LCR_PARTIAL_FASTER, // 部分 hash id 更快
        LCR_FULLY_FASTER    // 完全比这个 locator 快（包括相等）
    };

    // 文档信息：记录文档在数据源中的位置
    struct DocInfo {
        int64_t timestamp;        // 时间戳
        uint32_t concurrentIdx;   // 并发索引（时间戳相同时的序号）
        uint16_t hashId;          // Hash ID（用于分片）
        uint8_t sourceIdx;        // 数据源索引
    };

private:
    uint64_t _src;                              // 数据源标识
    base::Progress::Offset _minOffset;          // 最小偏移量
    base::MultiProgress _multiProgress;        // 多进度信息（每个 hashId 的进度）
    std::string _userData;                      // 用户数据
    bool _isLegacyLocator;                     // 是否遗留 Locator
};
```

**Locator 的关键字段**：

![Locator 的完整结构：包含所有关键字段和 DocInfo 结构](/images/diagrams/indexlib-locator-complete-structure.svg)

- **_src**：数据源标识，用于区分不同的数据源
- **_minOffset**：最小偏移量，记录最小的 timestamp 和 concurrentIdx
- **_multiProgress**：多进度信息，每个 hashId 记录自己的进度
- **_userData**：用户数据，可以存储自定义信息
- **_isLegacyLocator**：是否遗留 Locator，用于兼容旧版本

### 1.2 Progress 结构

`Progress` 是进度信息，定义在 `base/Progress.h` 中：

```cpp
// base/Progress.h
struct Progress {
    using Offset = std::pair<int64_t, uint32_t>;  // (timestamp, concurrentIdx)
    static constexpr Offset INVALID_OFFSET = {-1, 0};
    static constexpr Offset MIN_OFFSET = {0, 0};
    
    Progress(uint32_t from, uint32_t to, const Offset& offset);
    
    uint32_t from;      // HashId 范围起始
    uint32_t to;        // HashId 范围结束
    Offset offset;      // 偏移量（timestamp, concurrentIdx）
};

typedef std::vector<Progress> ProgressVector;      // 一个 hashId 范围的进度列表
typedef std::vector<ProgressVector> MultiProgress;  // 多个 hashId 范围的进度列表
```

**Progress 的关键字段**：

![Progress 的结构：包含 from、to、offset 等字段](/images/diagrams/indexlib-progress-structure.svg)

- **from/to**：HashId 范围，用于分片处理
- **offset**：偏移量，包含 timestamp 和 concurrentIdx
- **ProgressVector**：一个 hashId 范围的进度列表
- **MultiProgress**：多个 hashId 范围的进度列表

### 1.3 DocInfo 结构

`DocInfo` 是文档信息，记录文档在数据源中的位置：

![DocInfo 的结构：包含 timestamp、concurrentIdx、hashId、sourceIdx 等字段](/images/diagrams/indexlib-docinfo-structure.svg)

**DocInfo 的关键字段**：
- **timestamp**：时间戳，记录数据的时间位置
- **concurrentIdx**：并发索引，处理时间戳相同的情况
- **hashId**：Hash ID，用于分片
- **sourceIdx**：数据源索引，支持多数据源

## 2. Locator 的比较逻辑

### 2.1 IsFasterThan() 方法

`IsFasterThan()` 是 Locator 比较的核心方法：

![IsFasterThan() 方法：比较两个 Locator 的实现逻辑](/images/diagrams/indexlib-locator-compare-logic.svg)

**比较逻辑**：
1. **检查数据源**：检查两个 Locator 是否来自同一数据源
2. **比较 MultiProgress**：比较每个 hashId 的进度
3. **返回比较结果**：返回 LCR_INVALID、LCR_SLOWER、LCR_PARTIAL_FASTER 或 LCR_FULLY_FASTER

### 2.2 比较结果的语义

Locator 比较结果的语义：

![Locator 比较结果的语义：不同结果的含义和应用场景](/images/diagrams/indexlib-locator-compare-result-semantics.svg)

**比较结果**：
- **LCR_INVALID**：数据源不同，无法比较
- **LCR_SLOWER**：比目标 Locator 慢，数据未处理
- **LCR_PARTIAL_FASTER**：部分 hashId 更快，需要部分处理
- **LCR_FULLY_FASTER**：完全比目标 Locator 快，数据已处理

### 2.3 多进度比较

多进度比较的实现：

![多进度比较：比较 MultiProgress 中每个 hashId 的进度](/images/diagrams/indexlib-multi-progress-compare.svg)

**比较流程**：
1. **遍历 MultiProgress**：遍历每个 hashId 的进度列表
2. **比较进度**：比较每个 hashId 的进度（timestamp 和 concurrentIdx）
3. **汇总结果**：汇总所有 hashId 的比较结果
4. **返回最终结果**：返回整体的比较结果

## 3. Locator 的更新机制

### 3.1 Update() 方法

`Update()` 方法用于更新 Locator：

![Update() 方法：更新 Locator 的实现逻辑](/images/diagrams/indexlib-locator-update-logic.svg)

**更新逻辑**：
- **条件检查**：只有当新的 Locator 完全比当前 Locator 快时，才更新
- **更新 MultiProgress**：更新 `_multiProgress`，记录最新的数据处理位置
- **更新 MinOffset**：更新 `_minOffset`，记录最小的偏移量
- **保证一致性**：保证 Locator 只向前推进，不会回退

### 3.2 更新时机

Locator 的更新时机：

![Locator 的更新时机：在数据处理完成后更新 Locator](/images/diagrams/indexlib-locator-update-timing.svg)

**更新时机**：
- **数据处理完成**：处理完一批数据后更新 Locator
- **Segment 构建完成**：Segment 构建完成后更新 Locator
- **版本提交时**：版本提交时更新 Version 的 Locator
- **增量更新时**：增量更新时更新 Locator，记录处理位置

## 4. Locator 的序列化

### 4.1 Serialize() 方法

`Serialize()` 方法用于序列化 Locator：

![Locator 的序列化：将 Locator 序列化为字符串](/images/diagrams/indexlib-locator-serialize.svg)

**序列化内容**：
- **Magic Number**：魔数，用于验证
- **Version**：版本号，用于兼容性
- **Src**：数据源标识
- **MultiProgress**：多进度信息
- **UserData**：用户数据

### 4.2 Deserialize() 方法

`Deserialize()` 方法用于反序列化 Locator：

![Locator 的反序列化：从字符串反序列化为 Locator](/images/diagrams/indexlib-locator-deserialize.svg)

**反序列化流程**：
1. **验证 Magic Number**：验证魔数，确保数据格式正确
2. **读取 Version**：读取版本号，根据版本号选择解析方式
3. **读取数据**：读取 Src、MultiProgress、UserData 等数据
4. **验证数据**：验证数据的有效性
5. **构建 Locator**：构建 Locator 对象

## 5. 数据一致性保证

### 5.1 数据不重复保证

通过 Locator 保证数据不重复：

![数据不重复保证：通过 Locator 比较避免重复处理数据](/images/diagrams/indexlib-data-no-duplicate.svg)

**保证机制**：
- **Locator 比较**：通过 `IsFasterThan()` 判断数据是否已处理
- **跳过已处理数据**：如果数据已处理（LCR_FULLY_FASTER），则跳过
- **只处理新数据**：只处理未处理的数据（LCR_SLOWER），避免重复处理

### 5.2 数据不丢失保证

通过 Locator 保证数据不丢失：

![数据不丢失保证：通过 Locator 记录处理位置，保证数据不丢失](/images/diagrams/indexlib-data-no-lost.svg)

**保证机制**：
- **记录处理位置**：通过 Locator 记录数据处理位置
- **增量更新**：通过 Locator 实现增量更新，只处理新数据
- **故障恢复**：故障恢复时，通过 Locator 判断需要重新处理的数据
- **版本一致性**：通过 Version 的 Locator 保证版本数据的一致性

### 5.3 多数据源一致性

多数据源场景下的数据一致性：

![多数据源一致性：通过 sourceIdx 区分数据源，保证多数据源场景的数据一致性](/images/diagrams/indexlib-multi-source-consistency.svg)

**保证机制**：
- **数据源标识**：通过 `_src` 和 `sourceIdx` 区分数据源
- **独立 Locator**：每个数据源有独立的 Locator
- **独立处理**：每个数据源独立处理，互不干扰
- **统一管理**：通过 Version 统一管理所有数据源的 Locator

## 6. Locator 的高级特性

### 6.1 分片处理支持

Locator 支持分片处理：

![分片处理支持：通过 hashId 支持分片处理](/images/diagrams/indexlib-locator-sharding.svg)

**分片机制**：
- **HashId 范围**：通过 Progress 的 from/to 定义 HashId 范围
- **独立进度**：每个 HashId 范围有独立的进度
- **并行处理**：不同 HashId 范围可以并行处理
- **进度追踪**：通过 MultiProgress 追踪每个 HashId 范围的进度

### 6.2 并发控制

Locator 支持并发控制：

![并发控制：通过 concurrentIdx 处理时间戳相同的情况](/images/diagrams/indexlib-locator-concurrency.svg)

**并发机制**：
- **Timestamp**：时间戳，记录数据的时间位置
- **ConcurrentIdx**：并发索引，处理时间戳相同的情况
- **两级定位**：通过 timestamp 和 concurrentIdx 两级定位，保证顺序性
- **并发安全**：Locator 的比较和更新支持并发，保证线程安全

### 6.3 用户数据支持

Locator 支持用户数据：

![用户数据支持：通过 _userData 存储自定义信息](/images/diagrams/indexlib-locator-user-data.svg)

**用户数据机制**：
- **自定义信息**：通过 `_userData` 存储自定义信息
- **序列化支持**：用户数据会序列化到 Locator 中
- **查询支持**：可以通过 `GetUserData()` 获取用户数据
- **灵活扩展**：支持存储任意字符串数据

## 7. Locator 的实际应用

### 7.1 实时写入场景

在实时写入场景中，Locator 的应用：

![实时写入场景中的 Locator：通过 Locator 判断数据是否已处理](/images/diagrams/indexlib-locator-realtime-application.svg)

**应用流程**：
1. **接收数据**：实时接收数据流
2. **检查 Locator**：通过 `IsFasterThan()` 判断数据是否已处理
3. **处理新数据**：只处理未处理的数据
4. **更新 Locator**：处理完成后更新 Locator
5. **提交版本**：定期提交版本，更新 Version 的 Locator

### 7.2 批量更新场景

在批量更新场景中，Locator 的应用：

![批量更新场景中的 Locator：批量处理数据，避免重复处理](/images/diagrams/indexlib-locator-batch-application.svg)

**应用流程**：
1. **读取数据源**：从数据源批量读取数据
2. **检查 Locator**：通过 `IsFasterThan()` 判断哪些数据已处理
3. **过滤已处理数据**：过滤掉已处理的数据
4. **处理新数据**：只处理未处理的数据
5. **更新 Locator**：处理完成后更新 Locator
6. **提交版本**：批量处理完成后提交版本

### 7.3 故障恢复场景

在故障恢复场景中，Locator 的应用：

![故障恢复场景中的 Locator：通过 Locator 判断需要重新处理的数据](/images/diagrams/indexlib-locator-recovery-application.svg)

**应用流程**：
1. **加载版本**：加载故障前的版本，获取 Locator
2. **读取数据源**：从数据源读取数据
3. **检查 Locator**：通过 `IsFasterThan()` 判断哪些数据已处理
4. **重新处理**：只重新处理未处理的数据
5. **更新 Locator**：处理完成后更新 Locator
6. **提交版本**：恢复完成后提交版本

## 8. Locator 的性能优化

### 8.1 比较性能优化

Locator 比较的性能优化：

![Locator 比较的性能优化：优化比较算法，提高比较效率](/images/diagrams/indexlib-locator-compare-optimization.svg)

**优化策略**：
- **快速路径**：对于常见情况使用快速路径
- **缓存结果**：缓存比较结果，避免重复比较
- **并行比较**：支持并行比较多个 Locator
- **算法优化**：优化比较算法，减少比较次数

### 8.2 序列化性能优化

Locator 序列化的性能优化：

![Locator 序列化的性能优化：优化序列化格式，提高序列化效率](/images/diagrams/indexlib-locator-serialize-optimization.svg)

**优化策略**：
- **紧凑格式**：使用紧凑的序列化格式，减少序列化大小
- **压缩支持**：支持压缩序列化数据，减少存储空间
- **批量序列化**：支持批量序列化，提高序列化效率
- **版本兼容**：支持版本兼容，平滑升级

## 9. Locator 的关键设计

### 9.1 设计原则

Locator 的设计原则：

![Locator 的设计原则：简单、高效、可靠的设计原则](/images/diagrams/indexlib-locator-design-principles.svg)

**设计原则**：
- **简单性**：设计简单，易于理解和实现
- **高效性**：比较和更新操作高效，不影响性能
- **可靠性**：保证数据一致性，不重复、不丢失
- **扩展性**：支持多数据源、分片处理等扩展功能

### 9.2 兼容性设计

Locator 的兼容性设计：

![Locator 的兼容性设计：支持遗留 Locator 和版本兼容](/images/diagrams/indexlib-locator-compatibility.svg)

**兼容性机制**：
- **遗留 Locator**：支持遗留 Locator，通过 `_isLegacyLocator` 标识
- **版本兼容**：支持不同版本的 Locator，通过版本号区分
- **平滑升级**：支持平滑升级，不影响已有数据
- **向后兼容**：保证向后兼容，旧版本可以读取新版本数据

### 9.3 线程安全设计

Locator 的线程安全设计：

![Locator 的线程安全设计：支持并发访问，保证线程安全](/images/diagrams/indexlib-locator-thread-safety.svg)

**线程安全机制**：
- **原子操作**：使用原子操作保证线程安全
- **无锁设计**：尽可能使用无锁设计，提高并发性能
- **读写分离**：支持读写分离，提高并发度
- **并发控制**：通过 concurrentIdx 支持并发控制

## 10. 小结

Locator 与数据一致性是 IndexLib 的核心功能，通过 Locator 实现增量更新和数据一致性保证。通过本文的深入解析，我们了解到：

**关键要点**：
- **Locator 结构**：包含数据源标识、多进度信息、用户数据等关键字段
- **比较逻辑**：通过 `IsFasterThan()` 判断数据是否已处理，支持多种比较结果
- **更新机制**：通过 `Update()` 更新 Locator，保证只向前推进
- **序列化支持**：支持序列化和反序列化，持久化到磁盘
- **数据一致性保证**：通过 Locator 保证数据不重复、不丢失，支持多数据源场景
- **高级特性**：支持分片处理、并发控制、用户数据等高级特性
- **性能优化**：通过算法优化、格式优化等策略提高性能
- **设计原则**：简单、高效、可靠、可扩展的设计原则

理解 Locator 与数据一致性，是掌握 IndexLib 数据管理机制的关键。在下一篇文章中，我们将深入介绍文件系统抽象与存储格式的实现细节。
