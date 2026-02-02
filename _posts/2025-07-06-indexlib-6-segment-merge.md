---
layout: single
title: "IndexLib（6）：Segment 合并策略"
series: indexlib
permalink: /indexlib-6-segment-merge/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-07-06
---

在上一篇文章中，我们深入了解了版本管理和增量更新的机制。本文将继续深入，详细解析 Segment 合并策略的实现，这是理解 IndexLib 如何优化索引结构和提高查询性能的关键。

![Segment 合并策略概览：从合并策略到合并执行的完整流程](/images/diagrams/indexlib-segment-merge-overview.svg)

## 1. Segment 合并概览

### 1.1 合并的目的

Segment 合并的主要目的包括：

1. **减少 Segment 数量**：合并多个小 Segment 为一个大 Segment，减少查询时需要遍历的 Segment 数量
2. **优化查询性能**：减少 Segment 数量可以降低查询延迟，提高查询吞吐量
3. **释放存储空间**：合并可以删除重复数据，释放存储空间
4. **优化索引结构**：合并可以优化索引结构，提高索引效率

让我们先通过图来理解 Segment 合并的整体流程：

![Segment 合并流程：从合并策略到合并执行的完整过程](/images/diagrams/indexlib-segment-merge-flow.svg)

**Segment 合并流程图**：

```mermaid
graph TD
    A[开始合并] --> B[获取当前版本]
    B --> C[选择合并策略]
    C --> D{MergeStrategy}
    D -->|OptimizeMergeStrategy| E[选择需要合并的 Segment]
    D -->|其他策略| F[其他合并策略]
    E --> G[创建 MergePlan]
    F --> G
    G --> H[验证 MergePlan]
    H --> I{验证通过?}
    I -->|否| J[调整策略]
    J --> C
    I -->|是| K[执行合并]
    K --> L[创建 IndexMergeOperation]
    L --> M[读取源 Segment]
    M --> N[合并索引数据]
    N --> O[写入目标 Segment]
    O --> P[创建新版本]
    P --> Q[提交新版本]
    Q --> R[清理旧 Segment]
    R --> S[完成合并]
    style C fill:#e3f2fd
    style K fill:#fff3e0
    style P fill:#f3e5f5
    style Q fill:#e8f5e9
```

### 1.2 合并的核心组件

Segment 合并包括以下核心组件：

- **MergeStrategy**：合并策略，决定哪些 Segment 参与合并
- **MergePlan**：合并计划，包含合并的 Segment 列表和目标 Segment 信息
- **IndexMergeOperation**：合并操作，执行实际的合并工作
- **VersionMerger**：版本合并器，管理合并流程和版本更新

## 2. MergeStrategy：合并策略

### 2.1 MergeStrategy 接口

`MergeStrategy` 是合并策略的抽象接口，定义在 `table/index_task/merger/MergeStrategy.h` 中：

```cpp
// table/index_task/merger/MergeStrategy.h
class MergeStrategy
{
public:
    virtual ~MergeStrategy() {}
    
    // 获取策略名称
    virtual std::string GetName() const = 0;
    
    // 创建合并计划：根据 Context 创建合并计划
    virtual std::pair<Status, std::shared_ptr<MergePlan>>
    CreateMergePlan(const framework::IndexTaskContext* context) = 0;
};
```

**MergeStrategy 的关键方法**：

![MergeStrategy 接口：提供合并策略的抽象](/images/diagrams/indexlib-merge-strategy-interface.svg)

- **GetName()**：获取策略名称，用于标识不同的合并策略
- **CreateMergePlan()**：根据 IndexTaskContext 创建合并计划，决定哪些 Segment 参与合并

### 2.2 合并策略类型

IndexLib 支持多种合并策略：

![合并策略类型：Optimize、Realtime、ShardBased 等](/images/diagrams/indexlib-merge-strategy-types.svg)

**合并策略类型**：
- **OptimizeMergeStrategy**：优化合并策略，合并所有符合条件的 Segment
- **RealtimeMergeStrategy**：实时合并策略，实时合并小 Segment
- **ShardBasedMergeStrategy**：分片合并策略，按分片合并 Segment
- **KeyValueOptimizeMergeStrategy**：KV 优化合并策略，针对 KV 表的优化合并

### 2.3 OptimizeMergeStrategy：优化合并策略

`OptimizeMergeStrategy` 是优化合并策略的实现，定义在 `table/index_task/merger/OptimizeMergeStrategy.h` 中：

```cpp
// table/index_task/merger/OptimizeMergeStrategy.h
class OptimizeMergeStrategy : public MergeStrategy
{
public:
    std::string GetName() const override { 
        return MergeStrategyDefine::OPTIMIZE_MERGE_STRATEGY_NAME; 
    }
    
    // 创建合并计划
    std::pair<Status, std::shared_ptr<MergePlan>>
    CreateMergePlan(const framework::IndexTaskContext* context) override;

private:
    // 合并参数
    struct OptimizeMergeParams {
        uint32_t maxDocCount;                    // 参与合并的 Segment 的最大文档数
        uint64_t afterMergeMaxDocCount;         // 合并后的最小文档数
        uint32_t afterMergeMaxSegmentCount;     // 合并后的最大 Segment 数
        bool skipSingleMergedSegment;           // 是否跳过单个已合并的 Segment
    };
    
    OptimizeMergeParams _params;
};
```

**OptimizeMergeStrategy 的关键参数**：

![OptimizeMergeStrategy 参数：控制合并行为的关键参数](/images/diagrams/indexlib-optimize-merge-params.svg)

- **maxDocCount**：参与合并的 Segment 的最大文档数，只有小于等于该值的 Segment 才会参与合并
- **afterMergeMaxDocCount**：合并后的最小文档数，控制合并后 Segment 的大小
- **afterMergeMaxSegmentCount**：合并后的最大 Segment 数，控制合并后 Segment 的数量
- **skipSingleMergedSegment**：是否跳过单个已合并的 Segment，避免重复合并

### 2.4 合并策略的选择逻辑

合并策略的选择逻辑：

![合并策略的选择逻辑：根据 Segment 特征选择合并策略](/images/diagrams/indexlib-merge-strategy-selection.svg)

**选择逻辑**：
1. **收集源 Segment**：从 TabletData 中收集符合条件的 Segment
2. **过滤 Segment**：根据 `maxDocCount` 过滤 Segment，只保留符合条件的 Segment
3. **分组 Segment**：根据 `afterMergeMaxDocCount` 和 `afterMergeMaxSegmentCount` 分组 Segment
4. **创建合并计划**：为每组 Segment 创建合并计划

## 3. MergePlan：合并计划

### 3.1 MergePlan 的结构

`MergePlan` 是合并计划，定义在 `table/index_task/merger/MergePlan.h` 中：

```cpp
// table/index_task/merger/MergePlan.h
class MergePlan : public framework::IndexTaskResource, 
                  public autil::legacy::Jsonizable
{
public:
    // 添加合并计划
    void AddMergePlan(const SegmentMergePlan& segmentMergePlan);
    
    // 获取合并计划
    const SegmentMergePlan& GetSegmentMergePlan(size_t index);
    
    // 获取目标版本
    const framework::Version& GetTargetVersion() const;
    void SetTargetVersion(framework::Version targetVersion);
    
    // 创建新版本
    static framework::Version CreateNewVersion(
        const std::shared_ptr<MergePlan>& mergePlan,
        const framework::IndexTaskContext* taskContext);

private:
    std::vector<SegmentMergePlan> _mergePlan;  // 合并计划列表
    framework::Version _targetVersion;          // 目标版本
};
```

**MergePlan 的关键字段**：

![MergePlan 的结构：包含 SegmentMergePlan 列表和目标版本](/images/diagrams/indexlib-merge-plan-structure.svg)

- **SegmentMergePlan 列表**：每个 SegmentMergePlan 包含一组要合并的 Segment
- **目标版本**：合并后的目标版本，包含合并后的 Segment 列表

### 3.2 SegmentMergePlan：Segment 合并计划

`SegmentMergePlan` 是单个 Segment 合并计划：

```cpp
// table/index_task/merger/SegmentMergePlan.h
class SegmentMergePlan
{
public:
    // 添加源 Segment
    void AddSrcSegment(segmentid_t segmentId);
    
    // 设置目标 Segment
    void SetTargetSegment(segmentid_t segmentId);
    
    // 获取源 Segment 列表
    const std::vector<segmentid_t>& GetSrcSegments() const;
    
    // 获取目标 Segment
    segmentid_t GetTargetSegment() const;

private:
    std::vector<segmentid_t> _srcSegments;  // 源 Segment 列表
    segmentid_t _targetSegment;            // 目标 Segment
};
```

**SegmentMergePlan 的关键字段**：

![SegmentMergePlan 的结构：包含源 Segment 列表和目标 Segment](/images/diagrams/indexlib-segment-merge-plan-structure.svg)

- **源 Segment 列表**：要合并的 Segment 列表
- **目标 Segment**：合并后的目标 Segment

### 3.3 合并计划的创建流程

合并计划的创建流程：

![合并计划的创建流程：从收集 Segment 到创建合并计划](/images/diagrams/indexlib-merge-plan-creation.svg)

**创建流程**：
1. **收集源 Segment**：从 TabletData 中收集符合条件的 Segment
2. **过滤 Segment**：根据合并参数过滤 Segment
3. **分组 Segment**：根据合并参数分组 Segment
4. **创建 SegmentMergePlan**：为每组 Segment 创建 SegmentMergePlan
5. **设置目标 Segment**：为每个 SegmentMergePlan 设置目标 Segment
6. **创建 MergePlan**：将所有 SegmentMergePlan 添加到 MergePlan
7. **设置目标版本**：设置合并后的目标版本

## 4. 合并执行流程

### 4.1 VersionMerger：版本合并器

`VersionMerger` 是版本合并器，管理合并流程和版本更新，定义在 `framework/VersionMerger.h` 中：

```cpp
// framework/VersionMerger.h
class VersionMerger
{
public:
    // 执行合并任务
    future_lite::coro::Lazy<std::pair<Status, versionid_t>>
    ExecuteTask(const Version& sourceVersion, 
                const std::string& taskType,
                const std::string& taskName,
                const std::map<std::string, std::string>& params);
    
    // 运行合并流程
    future_lite::coro::Lazy<std::pair<Status, versionid_t>> Run();
    
    // 获取合并后的版本信息
    std::shared_ptr<MergedVersionInfo> GetMergedVersionInfo();
    
    // 判断是否需要提交
    bool NeedCommit() const;

private:
    std::string _tabletName;
    std::shared_ptr<ITabletMergeController> _controller;
    std::unique_ptr<IIndexTaskPlanCreator> _planCreator;
    Version _currentBaseVersion;
    std::shared_ptr<MergedVersionInfo> _mergedVersionInfo;
};
```

**VersionMerger 的关键组件**：

![VersionMerger 的结构：管理合并流程和版本更新](/images/diagrams/indexlib-version-merger-structure.svg)

- **MergeController**：合并控制器，管理合并任务的执行
- **PlanCreator**：计划创建器，创建合并计划
- **MergedVersionInfo**：合并后的版本信息，包含基础版本和目标版本

### 4.2 合并执行流程

合并执行的完整流程：

![合并执行流程：从创建合并计划到提交新版本](/images/diagrams/indexlib-merge-execution-flow.svg)

**执行流程**：
1. **检查合并条件**：判断是否需要合并（Segment 数量、大小等）
2. **创建合并计划**：调用 MergeStrategy 创建合并计划
3. **提交合并任务**：将合并任务提交到 MergeController
4. **执行合并操作**：执行 IndexMergeOperation，合并 Segment
5. **创建新版本**：合并完成后创建新版本
6. **提交新版本**：提交新版本，更新 TabletData

### 4.3 IndexMergeOperation：合并操作

`IndexMergeOperation` 是合并操作，执行实际的合并工作：

![IndexMergeOperation：执行实际的合并工作](/images/diagrams/indexlib-index-merge-operation.svg)

**合并操作的关键步骤**：
1. **读取源 Segment**：读取所有源 Segment 的数据
2. **合并索引**：合并倒排索引、正排索引等
3. **合并文档**：合并文档数据，去重、排序等
4. **写入目标 Segment**：将合并后的数据写入目标 Segment
5. **更新元数据**：更新 Segment 的元数据信息

## 5. 合并策略详解

### 5.1 OptimizeMergeStrategy 的合并逻辑

OptimizeMergeStrategy 的合并逻辑：

![OptimizeMergeStrategy 的合并逻辑：根据参数决定合并行为](/images/diagrams/indexlib-optimize-merge-logic.svg)

**合并逻辑**：
1. **收集源 Segment**：从 TabletData 中收集所有符合条件的 Segment
2. **过滤 Segment**：根据 `maxDocCount` 过滤，只保留文档数小于等于该值的 Segment
3. **计算目标 Segment 数**：根据 `afterMergeMaxDocCount` 和 `afterMergeMaxSegmentCount` 计算目标 Segment 数
4. **分组 Segment**：将 Segment 分组，每组合并为一个目标 Segment
5. **创建合并计划**：为每组 Segment 创建 SegmentMergePlan

### 5.2 合并参数的影响

合并参数对合并行为的影响：

![合并参数的影响：maxDocCount、afterMergeMaxDocCount 等参数的作用](/images/diagrams/indexlib-merge-params-impact.svg)

**参数影响**：
- **maxDocCount**：控制哪些 Segment 参与合并，较大的值会包含更多 Segment
- **afterMergeMaxDocCount**：控制合并后 Segment 的大小，较大的值会产生更大的 Segment
- **afterMergeMaxSegmentCount**：控制合并后 Segment 的数量，较小的值会产生更少的 Segment
- **skipSingleMergedSegment**：控制是否跳过单个已合并的 Segment，避免重复合并

### 5.3 合并策略的选择

不同场景下的合并策略选择：

![合并策略的选择：根据场景选择不同的合并策略](/images/diagrams/indexlib-merge-strategy-choice.svg)

**策略选择**：
- **OptimizeMergeStrategy**：适用于全量合并，合并所有符合条件的 Segment
- **RealtimeMergeStrategy**：适用于实时合并，实时合并小 Segment
- **ShardBasedMergeStrategy**：适用于分片场景，按分片合并 Segment
- **KeyValueOptimizeMergeStrategy**：适用于 KV 表，针对 KV 表的优化合并

## 6. 合并的触发条件

### 6.1 合并触发条件

合并的触发条件：

![合并触发条件：Segment 数量、大小等条件](/images/diagrams/indexlib-merge-trigger-conditions.svg)

**触发条件**：
- **Segment 数量**：当 Segment 数量超过阈值时触发合并
- **Segment 大小**：当小 Segment 数量过多时触发合并
- **查询性能**：当查询性能下降时触发合并
- **存储空间**：当存储空间不足时触发合并
- **手动触发**：支持手动触发合并

### 6.2 合并时机的选择

合并时机的选择：

![合并时机的选择：在线合并、离线合并等](/images/diagrams/indexlib-merge-timing.svg)

**合并时机**：
- **在线合并**：在服务运行期间进行合并，不影响服务可用性
- **离线合并**：在服务停止时进行合并，可以更彻底地优化索引
- **定时合并**：定期触发合并，保持索引结构优化
- **按需合并**：根据查询性能或存储空间按需触发合并

## 7. 合并的性能优化

### 7.1 合并性能优化策略

合并性能优化的策略：

![合并性能优化：并行合并、增量合并等策略](/images/diagrams/indexlib-merge-performance-optimization.svg)

**优化策略**：
- **并行合并**：多个 Segment 可以并行合并，提高合并效率
- **增量合并**：只合并变更的 Segment，减少合并工作量
- **合并优先级**：根据 Segment 大小和重要性设置合并优先级
- **资源控制**：控制合并时的 CPU、内存、IO 资源使用

### 7.2 合并的资源控制

合并时的资源控制：

![合并的资源控制：CPU、内存、IO 资源的控制](/images/diagrams/indexlib-merge-resource-control.svg)

**资源控制**：
- **CPU 控制**：限制合并时的 CPU 使用率，避免影响查询性能
- **内存控制**：限制合并时的内存使用，避免内存溢出
- **IO 控制**：限制合并时的 IO 带宽，避免影响查询 IO
- **并发控制**：控制同时进行的合并任务数量

## 8. 合并的实际应用

### 8.1 全量合并场景

在全量合并场景中，合并的应用：

![全量合并场景：合并所有符合条件的 Segment](/images/diagrams/indexlib-merge-full-scenario.svg)

**全量合并流程**：
1. **收集所有 Segment**：收集所有符合条件的 Segment
2. **创建合并计划**：创建合并计划，将所有 Segment 合并为少数几个大 Segment
3. **执行合并**：执行合并操作，合并所有 Segment
4. **提交新版本**：提交新版本，更新 TabletData

### 8.2 增量合并场景

在增量合并场景中，合并的应用：

![增量合并场景：只合并新增或变更的 Segment](/images/diagrams/indexlib-merge-incremental-scenario.svg)

**增量合并流程**：
1. **识别变更 Segment**：识别新增或变更的 Segment
2. **创建合并计划**：创建合并计划，只合并变更的 Segment
3. **执行合并**：执行合并操作，合并变更的 Segment
4. **提交新版本**：提交新版本，更新 TabletData

## 9. 合并的关键设计

### 9.1 合并的原子性

合并的原子性保证：

![合并的原子性：通过 Fence 机制保证合并的原子性](/images/diagrams/indexlib-merge-atomicity.svg)

**原子性保证**：
- **Fence 机制**：通过 Fence 目录保证合并的原子性
- **事务性提交**：合并完成后原子性地提交新版本
- **错误恢复**：如果合并失败，可以回滚，不影响已有版本

### 9.2 合并的一致性

合并的一致性保证：

![合并的一致性：保证合并后数据的一致性](/images/diagrams/indexlib-merge-consistency.svg)

**一致性保证**：
- **数据完整性**：保证合并后数据的完整性，不丢失数据
- **索引一致性**：保证合并后索引的一致性，索引结构正确
- **版本一致性**：保证合并后版本的一致性，版本信息正确

### 9.3 合并的性能优化

合并的性能优化：

![合并的性能优化：并行合并、资源控制等优化策略](/images/diagrams/indexlib-merge-performance.svg)

**性能优化**：
- **并行合并**：多个 Segment 可以并行合并，提高合并效率
- **增量合并**：只合并变更的 Segment，减少合并工作量
- **资源控制**：控制合并时的资源使用，避免影响查询性能
- **合并优先级**：根据 Segment 重要性设置合并优先级

## 10. 小结

Segment 合并策略是 IndexLib 的核心功能，通过 MergeStrategy 和 MergePlan 实现。通过本文的深入解析，我们了解到：

**关键要点**：
- **MergeStrategy**：合并策略，决定哪些 Segment 参与合并，支持多种合并策略
- **MergePlan**：合并计划，包含合并的 Segment 列表和目标 Segment 信息
- **OptimizeMergeStrategy**：优化合并策略，根据参数控制合并行为
- **合并执行流程**：从创建合并计划到提交新版本的完整流程
- **合并触发条件**：根据 Segment 数量、大小等条件触发合并
- **合并性能优化**：通过并行合并、资源控制等策略优化合并性能
- **合并的原子性和一致性**：通过 Fence 机制保证合并的原子性和一致性

理解 Segment 合并策略，是掌握 IndexLib 索引优化机制的关键。在下一篇文章中，我们将深入介绍内存管理与资源控制的实现细节。
