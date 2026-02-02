---
layout: single
title: "IndexLib（5）：版本管理与增量更新"
series: indexlib
permalink: /indexlib-5-version-management/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-07-05
---

在上一篇文章中，我们深入了解了查询流程的实现。本文将继续深入，详细解析版本管理和增量更新的机制，这是理解 IndexLib 如何管理索引版本和实现增量更新的关键。

![版本管理与增量更新概览：Version 与 Locator 的协同工作](/images/diagrams/indexlib-version-management-overview.svg)

## 1. 版本管理概览

### 1.1 版本管理的核心概念

IndexLib 的版本管理包括以下核心概念：

1. **Version**：版本信息，记录索引包含哪些 Segment
2. **Locator**：位置信息，记录数据处理的位置，用于增量更新
3. **版本演进**：每次 Commit 都会创建新版本，版本号递增
4. **增量更新**：通过 Locator 判断哪些数据已处理，避免重复处理

让我们先通过图来理解版本管理的整体架构：

![版本管理架构：Version、Locator、Segment 的关系](/images/diagrams/indexlib-version-architecture.svg)

### 1.2 版本管理的作用

版本管理在 IndexLib 中起到关键作用：

- **版本控制**：记录索引的演进历史，支持版本回滚
- **增量更新**：通过 Locator 判断哪些数据已处理，实现增量更新
- **Schema 演进**：支持 Schema 变更，每个 Segment 记录自己的 SchemaId
- **数据一致性**：保证数据不重复、不丢失，支持多数据源场景

## 2. Version：版本信息

### 2.1 Version 的结构

`Version` 记录索引的版本信息，定义在 `framework/Version.h` 中：

```cpp
// framework/Version.h
class Version : public autil::legacy::Jsonizable
{
private:
    struct SegmentInVersion {
        segmentid_t segmentId = INVALID_SEGMENTID;
        schemaid_t schemaId = DEFAULT_SCHEMAID;  // 每个 Segment 可以有不同的 Schema
    };

public:
    // 版本信息
    versionid_t GetVersionId() const { return _versionId; }
    void IncVersionId() { ++_versionId; }  // 每次 Commit 时递增
    
    // Segment 管理
    void AddSegment(segmentid_t segmentId, schemaid_t schemaId);
    void RemoveSegment(segmentid_t segmentId);
    size_t GetSegmentCount() const { return _segments.size(); }
    
    // Locator：数据位置信息
    void SetLocator(const Locator& locator);
    const Locator& GetLocator() const { return _locator; }
    
    // 时间戳
    void SetTimestamp(int64_t timestamp) { _timestamp = timestamp; }
    int64_t GetTimestamp() const { return _timestamp; }
    
    // 封存状态
    void SetSealed() { _sealed = true; }
    bool IsSealed() const { return _sealed; }

private:
    versionid_t _versionId;                    // 版本号，单调递增
    std::vector<SegmentInVersion> _segments;   // Segment 列表（有序）
    Locator _locator;                          // 位置信息，用于增量更新
    int64_t _timestamp;                        // 时间戳
    bool _sealed = false;                      // 是否封存
    schemaid_t _schemaId;                     // Schema ID
    std::string _fenceName;                    // Fence 名称
};
```

**Version 的关键字段**：

![Version 的结构：包含 VersionId、Segments、Locator 等关键信息](/images/diagrams/indexlib-version-structure.svg)

- **VersionId**：版本号，单调递增，每次 Commit 时递增
- **Segments**：该版本包含的 Segment 列表，每个 Segment 记录自己的 SchemaId
- **Locator**：数据位置信息，用于增量更新
- **Timestamp**：时间戳，记录版本创建时间
- **Sealed**：是否封存，封存后不再接收新 Segment

### 2.2 Version 的演进

每次 Commit 都会创建新版本，版本号递增：

![Version 演进：从 V1 到 V2 的版本变化](/images/diagrams/indexlib-version-evolution.svg)

**版本演进示例**：
- **V1**：包含 Segment [1, 2]，Locator 记录处理到 timestamp=100
- **V2**：新增 Segment 3，Locator 更新到 timestamp=200
- **V3**：Segment 1 和 2 合并为 Segment 4，Locator 更新到 timestamp=300

**版本演进的关键设计**：
- **版本号递增**：每次 Commit 时 `VersionId` 自动递增，保证版本顺序
- **Schema 演进**：每个 Segment 记录自己的 `SchemaId`，支持 Schema 变更
- **Locator 更新**：每次 Commit 时更新 Locator，记录最新的数据处理位置

### 2.3 Version 的持久化

Version 需要持久化到磁盘，通过 Fence 机制保证原子性：

![Version 持久化：通过 Fence 机制保证原子性](/images/diagrams/indexlib-version-persistence.svg)

**持久化流程**：
1. **创建 Fence 目录**：在提交前创建临时目录（Fence）
2. **写入 Version**：将 Version 写入 Fence 目录
3. **原子切换**：原子性地将 Fence 目录重命名为正式版本目录
4. **保证原子性**：要么全部成功，要么全部失败

### 2.4 Version 的加载

Version 的加载通过 `VersionLoader` 实现：

![Version 加载：从磁盘加载版本信息](/images/diagrams/indexlib-version-loading.svg)

**加载流程**：
1. **读取版本文件**：从磁盘读取版本文件（version.0、version.1 等）
2. **解析 Version**：解析 JSON 格式的版本信息
3. **验证 Version**：验证版本的有效性（Segment 是否存在等）
4. **加载 Segment**：根据 Version 中的 Segment 列表加载 Segment

## 3. Locator：位置信息

### 3.1 Locator 的作用

Locator 是增量更新的核心，记录数据的位置信息：

![Locator 的作用：记录数据处理位置，支持增量更新](/images/diagrams/indexlib-locator-role.svg)

**Locator 的关键作用**：
1. **增量更新**：通过 `IsFasterThan()` 判断哪些数据已处理，避免重复处理
2. **数据一致性**：保证数据不重复、不丢失，支持多数据源场景
3. **进度追踪**：记录每个 HashId 的处理进度，支持分片处理
4. **并发控制**：通过 `concurrentIdx` 处理时间戳相同的情况

### 3.2 Locator 的结构

`Locator` 的结构定义在 `framework/Locator.h` 中：

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

    // 比较两个 Locator：判断数据是否已处理
    LocatorCompareResult IsFasterThan(const Locator& other, 
                                      bool ignoreLegacyDiffSrc) const;

private:
    uint64_t _src;                              // 数据源标识
    base::Progress::Offset _minOffset;          // 最小偏移量
    base::MultiProgress _multiProgress;        // 多进度信息（每个 hashId 的进度）
    std::string _userData;                      // 用户数据
};
```

**Locator 的关键字段**：

![Locator 的结构：包含 timestamp、concurrentIdx、hashId 等信息](/images/diagrams/indexlib-locator-structure.svg)

- **timestamp**：时间戳，记录数据的时间位置
- **concurrentIdx**：并发索引，处理时间戳相同的情况
- **hashId**：Hash ID，用于分片
- **sourceIdx**：数据源索引，支持多数据源
- **multiProgress**：多进度信息，每个 hashId 记录自己的进度

### 3.3 Locator 的比较逻辑

Locator 的比较逻辑用于判断数据是否已处理：

![Locator 比较：判断数据是否已处理的逻辑](/images/diagrams/indexlib-locator-compare.svg)

**比较示例**：
- **Locator A**：timestamp=100, hashId=0
- **Locator B**：timestamp=200, hashId=0
- **结果**：B 比 A 快（`LCR_FULLY_FASTER`），说明 B 包含 A 的所有数据

**比较逻辑**：

```cpp
// framework/Locator.h
LocatorCompareResult Locator::IsFasterThan(const Locator& other, 
                                            bool ignoreLegacyDiffSrc) const
{
    // 1. 检查数据源是否相同
    if (!IsSameSrc(other, ignoreLegacyDiffSrc)) {
        return LCR_INVALID;
    }
    
    // 2. 比较每个 hashId 的进度
    for (size_t i = 0; i < _multiProgress.size(); ++i) {
        if (i >= other._multiProgress.size()) {
            return LCR_PARTIAL_FASTER;
        }
        
        // 比较该 hashId 的进度
        auto result = CompareProgress(_multiProgress[i], other._multiProgress[i]);
        if (result != LCR_FULLY_FASTER) {
            return result;
        }
    }
    
    return LCR_FULLY_FASTER;
}
```

### 3.4 Locator 的更新

Locator 的更新通过 `Update()` 方法实现：

![Locator 更新：更新数据处理位置](/images/diagrams/indexlib-locator-update.svg)

**更新逻辑**：
- **条件**：只有当新的 Locator 完全比当前 Locator 快时，才更新
- **更新内容**：更新 `multiProgress`，记录最新的数据处理位置
- **保证一致性**：保证 Locator 只向前推进，不会回退

## 4. 增量更新机制

### 4.1 增量更新的流程

增量更新通过 Locator 判断哪些数据已处理：

![增量更新流程：通过 Locator 判断数据是否已处理](/images/diagrams/indexlib-incremental-update-flow.svg)

**增量更新流程图**：

```mermaid
graph TD
    A[读取数据源] --> B[获取数据 Locator]
    B --> C[比较 Locator]
    C --> D{IsFasterThan?}
    D -->|LCR_FULLY_FASTER| E[数据已处理]
    D -->|LCR_SLOWER| F[处理新数据]
    D -->|LCR_PARTIAL_FASTER| G[部分处理]
    E --> H[跳过数据]
    F --> I[构建索引]
    G --> I
    I --> J[更新 Locator]
    J --> K[提交版本]
    K --> L[更新 Version Locator]
    style C fill:#e3f2fd
    style F fill:#fff3e0
    style J fill:#f3e5f5
    style K fill:#e8f5e9
```

**增量更新流程**：
1. **读取数据源**：从数据源读取数据
2. **检查 Locator**：通过 `IsFasterThan()` 判断数据是否已处理
3. **处理新数据**：只处理未处理的数据
4. **更新 Locator**：处理完成后更新 Locator
5. **提交版本**：Commit 时更新 Version 的 Locator

### 4.2 增量更新的判断

增量更新的判断通过 Locator 比较实现：

![增量更新判断：通过 Locator 比较判断数据是否已处理](/images/diagrams/indexlib-incremental-update-judge.svg)

**判断逻辑**：
- **LCR_FULLY_FASTER**：数据已处理，跳过
- **LCR_SLOWER**：数据未处理，需要处理
- **LCR_PARTIAL_FASTER**：部分数据已处理，需要部分处理
- **LCR_INVALID**：数据源不同，无法比较

### 4.3 增量更新的场景

增量更新适用于以下场景：

![增量更新场景：实时写入、批量更新等](/images/diagrams/indexlib-incremental-update-scenarios.svg)

**使用场景**：
- **实时写入**：实时接收数据，通过 Locator 判断哪些数据已处理
- **批量更新**：批量处理数据，通过 Locator 避免重复处理
- **多数据源**：从多个数据源读取数据，通过 Locator 保证数据一致性
- **故障恢复**：故障恢复时，通过 Locator 判断需要重新处理的数据

## 5. 版本提交与加载

### 5.1 版本提交流程

版本提交通过 `VersionCommitter` 实现：

![版本提交流程：从准备到持久化的完整过程](/images/diagrams/indexlib-version-commit-flow.svg)

**版本提交流程图**：

```mermaid
graph TD
    A[检查提交条件] --> B{需要提交?}
    B -->|否| C[跳过提交]
    B -->|是| D[准备版本信息]
    D --> E[收集 Segment]
    E --> F[准备 Locator]
    F --> G[创建 Fence]
    G --> H[写入版本文件]
    H --> I[更新版本号]
    I --> J[持久化到磁盘]
    J --> K[完成提交]
    style B fill:#e3f2fd
    style G fill:#fff3e0
    style I fill:#f3e5f5
    style J fill:#e8f5e9
```

**提交流程**：
1. **检查提交条件**：判断是否需要提交（有新的 Segment、有数据变更等）
2. **准备版本信息**：收集所有已构建的 Segment，准备 Locator
3. **创建 Fence**：创建 Fence 目录，保证原子性
4. **持久化 Version**：将 Version 写入 Fence 目录
5. **原子切换**：原子性地将 Fence 目录切换为正式版本目录
6. **更新 TabletData**：更新 TabletData 的 Version

### 5.2 版本加载流程

版本加载通过 `VersionLoader` 实现：

![版本加载流程：从磁盘加载版本信息](/images/diagrams/indexlib-version-load-flow.svg)

**加载流程**：
1. **读取版本文件**：从磁盘读取版本文件
2. **解析 Version**：解析 JSON 格式的版本信息
3. **验证 Version**：验证版本的有效性
4. **加载 Segment**：根据 Version 中的 Segment 列表加载 Segment
5. **初始化 TabletData**：初始化 TabletData，设置 Version 和 Segment 列表

### 5.3 版本回滚

版本回滚支持回滚到历史版本：

![版本回滚：回滚到历史版本](/images/diagrams/indexlib-version-rollback.svg)

**回滚流程**：
1. **选择目标版本**：选择要回滚到的目标版本
2. **验证版本**：验证目标版本的有效性
3. **加载版本**：加载目标版本的 Version 和 Segment
4. **更新 TabletData**：更新 TabletData，恢复到目标版本

## 6. Schema 演进

### 6.1 Schema 演进机制

IndexLib 支持 Schema 演进，每个 Segment 可以有不同的 Schema：

![Schema 演进：支持 Schema 变更，每个 Segment 记录自己的 SchemaId](/images/diagrams/indexlib-schema-evolution.svg)

**Schema 演进机制**：
- **Segment SchemaId**：每个 Segment 记录自己的 `SchemaId`
- **Schema 版本映射**：Version 维护 `SchemaVersionRoadMap`，记录 Schema 版本映射
- **兼容性检查**：Schema 变更时检查兼容性，保证数据一致性

### 6.2 Schema 变更流程

Schema 变更的流程：

![Schema 变更流程：从 Schema 变更到版本提交](/images/diagrams/indexlib-schema-change-flow.svg)

**变更流程**：
1. **检查兼容性**：检查新 Schema 与旧 Schema 的兼容性
2. **Seal 当前 Segment**：Seal 当前构建中的 Segment
3. **创建新 Segment**：使用新 Schema 创建新的 Segment
4. **提交版本**：Commit 时更新 SchemaId 和 SchemaVersionRoadMap

## 7. 版本清理

### 7.1 版本清理机制

版本清理用于清理不再需要的旧版本文件：

![版本清理：清理不再需要的旧版本文件](/images/diagrams/indexlib-version-cleanup.svg)

**清理机制**：
- **保留版本列表**：保留指定数量的版本，清理其他版本
- **清理 Segment**：清理不再被任何版本引用的 Segment
- **清理索引文件**：清理不再使用的索引文件

### 7.2 版本清理策略

版本清理的策略：

![版本清理策略：保留版本数量、清理时机等](/images/diagrams/indexlib-version-cleanup-strategy.svg)

**清理策略**：
- **保留版本数**：保留最近 N 个版本，清理其他版本
- **清理时机**：在 Commit 时或定期清理
- **清理范围**：清理版本文件、Segment 文件、索引文件等

## 8. 增量更新的实际应用

### 8.1 实时写入场景

在实时写入场景中，增量更新的应用：

![实时写入场景中的增量更新：通过 Locator 判断数据是否已处理](/images/diagrams/indexlib-incremental-realtime-scenario.svg)

**实时写入流程**：
1. **接收数据**：实时接收数据流
2. **检查 Locator**：通过 `IsFasterThan()` 判断数据是否已处理
3. **处理新数据**：只处理未处理的数据
4. **更新 Locator**：处理完成后更新 Locator
5. **提交版本**：定期 Commit，更新 Version 的 Locator

### 8.2 批量更新场景

在批量更新场景中，增量更新的应用：

![批量更新场景中的增量更新：批量处理数据，避免重复处理](/images/diagrams/indexlib-incremental-batch-scenario.svg)

**批量更新流程**：
1. **读取数据源**：从数据源批量读取数据
2. **检查 Locator**：通过 `IsFasterThan()` 判断哪些数据已处理
3. **过滤已处理数据**：过滤掉已处理的数据
4. **处理新数据**：只处理未处理的数据
5. **更新 Locator**：处理完成后更新 Locator
6. **提交版本**：批量处理完成后 Commit

## 9. 版本管理的关键设计

### 9.1 原子性保证

版本管理的原子性通过 Fence 机制保证：

![版本管理的原子性：通过 Fence 机制保证版本提交的原子性](/images/diagrams/indexlib-version-atomicity.svg)

**原子性保证**：
- **Fence 机制**：通过 Fence 目录保证版本提交的原子性
- **原子切换**：原子性地将 Fence 目录切换为正式版本目录
- **错误恢复**：如果提交失败，可以清理 Fence 目录，不影响已有版本

### 9.2 数据一致性

版本管理保证数据一致性：

![版本管理的数据一致性：通过 Locator 保证数据不重复、不丢失](/images/diagrams/indexlib-version-consistency.svg)

**数据一致性保证**：
- **Locator 比较**：通过 Locator 比较判断数据是否已处理
- **多数据源支持**：支持多数据源场景，通过 `sourceIdx` 区分数据源
- **并发控制**：通过 `concurrentIdx` 处理时间戳相同的情况

### 9.3 性能优化

版本管理的性能优化：

![版本管理的性能优化：版本缓存、懒加载等](/images/diagrams/indexlib-version-performance.svg)

**性能优化策略**：
- **版本缓存**：缓存常用版本，减少磁盘读取
- **懒加载**：按需加载版本信息，减少启动时间
- **批量操作**：批量处理版本操作，提高效率

## 10. 小结

版本管理和增量更新是 IndexLib 的核心功能，通过 Version 和 Locator 两个机制实现。通过本文的深入解析，我们了解到：

**关键要点**：
- **Version**：版本信息，记录索引包含哪些 Segment，支持版本演进和 Schema 演进
- **Locator**：位置信息，记录数据处理位置，用于增量更新和数据一致性保证
- **版本演进**：每次 Commit 都会创建新版本，版本号递增，支持版本回滚
- **增量更新**：通过 Locator 判断哪些数据已处理，避免重复处理，支持实时写入和批量更新
- **Schema 演进**：支持 Schema 变更，每个 Segment 记录自己的 SchemaId
- **原子性保证**：通过 Fence 机制保证版本提交的原子性
- **数据一致性**：通过 Locator 保证数据不重复、不丢失，支持多数据源场景

理解版本管理和增量更新，是掌握 IndexLib 数据管理机制的关键。在下一篇文章中，我们将深入介绍 Segment 合并策略的实现细节。
