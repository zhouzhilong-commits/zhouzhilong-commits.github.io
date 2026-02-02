---
layout: single
title: "IndexLib（3）：索引构建流程：Build、Flush、Seal、Commit"
series: indexlib
permalink: /indexlib-3-build-flow/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-07-03
---

在上一篇文章中，我们深入了解了 Tablet 和 Segment 的组织方式。本文将继续深入，详细解析索引构建的完整流程，这是理解 IndexLib 如何从文档构建索引的关键。

![索引构建完整流程：从 Build 到 Commit 的各个阶段](/images/diagrams/indexlib-build-complete-flow.svg)

**索引构建流程图**：

```mermaid
graph TD
    A[开始] --> B[接收文档批次]
    B --> C{Build 阶段}
    C --> D[文档验证]
    D --> E[分配 DocId]
    E --> F[写入 Indexer]
    F --> G[更新 SegmentInfo]
    G --> H{是否需要 Flush?}
    H -->|是| I[Flush 阶段]
    H -->|否| B
    I --> J[创建 SegmentDumper]
    J --> K[转储 MemSegment]
    K --> L[创建 DiskSegment]
    L --> M{是否需要 Seal?}
    M -->|是| N[Seal 阶段]
    M -->|否| B
    N --> O[封存 Segment]
    O --> P[标记为只读]
    P --> Q{是否需要 Commit?}
    Q -->|是| R[Commit 阶段]
    Q -->|否| B
    R --> S[准备新版本]
    S --> T[更新 Version]
    T --> U[持久化到磁盘]
    U --> V[完成]
    style C fill:#e3f2fd
    style I fill:#fff3e0
    style N fill:#f3e5f5
    style R fill:#e8f5e9
```

## 1. 索引构建流程概览

### 1.1 整体流程

IndexLib 的索引构建流程包括四个核心阶段：

1. **Build**：接收文档批次，构建索引到内存（MemSegment）
2. **Flush**：将内存数据刷新到磁盘，创建 DiskSegment
3. **Seal**：封存 Segment，标记为只读，准备合并
4. **Commit**：提交新版本，更新 Version，持久化到磁盘

让我们先通过图来理解整个流程：

![索引构建流程概览：Build、Flush、Seal、Commit 的关系](/images/diagrams/indexlib-build-flow-overview.svg)

**流程关系图**：

```mermaid
graph LR
    A[Build] -->|写入内存| B[MemSegment]
    B -->|触发转储| C[Flush]
    C -->|转储到磁盘| D[DiskSegment]
    D -->|封存| E[Seal]
    E -->|提交版本| F[Commit]
    F -->|更新| G[Version]
    G -->|持久化| H[磁盘]
    style A fill:#e3f2fd
    style C fill:#fff3e0
    style E fill:#f3e5f5
    style F fill:#e8f5e9
```

### 1.2 核心接口

索引构建的核心接口定义在 `framework/ITablet.h` 中：

```cpp
// framework/ITablet.h
class ITablet : private autil::NoCopyable
{
public:
    // 构建：接收文档批次并写入内存段
    virtual Status Build(const std::shared_ptr<document::IDocumentBatch>& batch) = 0;
    
    // 刷新：将内存数据刷新到磁盘
    virtual Status Flush() = 0;
    
    // 封存：封存当前 Segment，准备合并
    virtual Status Seal() = 0;
    
    // 提交版本：创建新版本并持久化
    virtual std::pair<Status, VersionMeta> Commit(const CommitOptions& commitOptions) = 0;
    
    // 判断是否需要提交
    virtual bool NeedCommit() const = 0;
};
```

**关键设计**：
- **Build**：持续构建，接收文档并写入 MemSegment
- **Flush**：触发转储，将 MemSegment 转为 DiskSegment
- **Seal**：封存 Segment，标记为只读，不再接收新文档
- **Commit**：提交版本，更新 Version，持久化到磁盘

## 2. Build：文档构建阶段

### 2.1 Build 流程

Build 阶段负责接收文档批次，将文档写入内存中的索引结构。让我们先通过图来理解 Build 流程：

![Build 流程：从文档批次到内存索引的构建过程](/images/diagrams/indexlib-build-process.svg)

Build 流程包括以下步骤：

1. **接收文档批次**：`Build()` 接收 `IDocumentBatch`
2. **文档验证**：验证文档格式、Schema 等
3. **分配 DocId**：为文档分配全局 DocId
4. **写入 Indexer**：将文档写入各个 Indexer（倒排索引、正排索引等）
5. **更新 SegmentInfo**：更新文档数量、Locator 等

### 2.2 TabletWriter::Build()

`TabletWriter` 是构建的核心实现，定义在 `framework/TabletWriter.h` 中：

```cpp
// framework/TabletWriter.h
class TabletWriter : private autil::NoCopyable
{
public:
    // 构建文档批次
    // 返回值：
    // - OK: 构建成功
    // - NoMem: 内存不足，需要等待内存释放
    // - NeedDump: 触发转储，需要转储并重新打开
    virtual Status Build(const std::shared_ptr<document::IDocumentBatch>& batch) = 0;
    
    // 创建转储器：准备转储 MemSegment
    virtual std::unique_ptr<SegmentDumper> CreateSegmentDumper() = 0;
    
    // 获取总内存使用
    virtual size_t GetTotalMemSize() const = 0;
    
    // 获取构建 Segment 转储所需的内存扩展大小
    virtual size_t GetBuildingSegmentDumpExpandSize() const = 0;
    
    // 判断是否有未提交的数据
    virtual bool IsDirty() const = 0;
};
```

**Build 的返回值**：
- **OK**：构建成功，可以继续构建
- **NoMem**：内存不足，需要等待内存释放或触发转储
- **NeedDump**：触发转储条件，需要转储并重新打开

### 2.3 文档的 DocId 分配

在 Build 阶段，需要为文档分配 DocId。关键代码（`table/normal_table/NormalTabletWriter.h`）：

```cpp
// table/normal_table/NormalTabletWriter.h
class NormalTabletWriter : public table::CommonTabletWriter
{
private:
    // 分发 DocId：为文档分配 DocId
    void DispatchDocIds(document::IDocumentBatch* batch);
    
    docid_t _buildingSegmentBaseDocId;  // 当前构建 Segment 的基础 DocId
    std::shared_ptr<NormalMemSegment> _normalBuildingSegment;  // 当前构建中的 Segment
};
```

**DocId 分配机制**：

![DocId 分配：全局 DocId 的计算和分配](/images/diagrams/indexlib-build-docid-allocation.svg)

- **BaseDocId**：当前 MemSegment 的全局 DocId 起始值
- **LocalDocId**：在 MemSegment 内的局部 DocId（从 0 开始递增）
- **GlobalDocId**：`baseDocId + localDocId`

### 2.4 文档写入 Indexer

文档写入各个 Indexer 的过程：

![文档写入 Indexer：倒排索引、正排索引等的构建](/images/diagrams/indexlib-build-write-indexer.svg)

**写入流程**：
1. **解析文档**：解析文档字段，提取索引字段
2. **写入倒排索引**：将 term 写入倒排索引
3. **写入正排索引**：将文档属性写入正排索引
4. **更新摘要**：更新文档摘要信息

### 2.5 内存控制

Build 阶段需要严格控制内存使用，避免内存溢出。关键机制：

![Build 内存控制：估算、评估、触发转储](/images/diagrams/indexlib-build-memory-control.svg)

**内存控制机制**：
- **估算内存**：`EstimateMemUsed()` 估算构建所需内存
- **评估内存**：`EvaluateCurrentMemUsed()` 评估当前实际内存使用
- **触发转储**：达到阈值时触发转储，释放内存

## 3. Flush：刷新到磁盘阶段

### 3.1 Flush 流程

Flush 阶段负责将内存数据刷新到磁盘，创建 DiskSegment。让我们先通过图来理解 Flush 流程：

![Flush 流程：从 MemSegment 到 DiskSegment 的转储过程](/images/diagrams/indexlib-flush-process.svg)

Flush 流程包括以下步骤：

1. **检查转储条件**：判断是否需要转储（内存阈值、文档数量等）
2. **创建 SegmentDumper**：创建转储器，准备转储任务
3. **创建转储参数**：计算转储所需的内存成本
4. **异步转储**：将内存数据写入磁盘
5. **创建 DiskSegment**：转储完成后创建 DiskSegment
6. **更新 TabletData**：更新 Segment 列表

### 3.2 转储条件判断

转储条件判断通过 `MemSegment::NeedDump()` 实现：

```cpp
// framework/MemSegment.h
class MemSegment : public Segment
{
public:
    // 是否需要转储：判断是否达到转储条件
    virtual bool NeedDump() const = 0;
    
    // 创建转储项：准备转储到磁盘
    virtual std::pair<Status, std::vector<std::shared_ptr<SegmentDumpItem>>> 
        CreateSegmentDumpItems() = 0;
};
```

**转储条件**：
- **内存阈值**：内存使用达到配置的阈值
- **文档数量**：文档数量达到配置的阈值
- **时间阈值**：构建时间达到配置的阈值

### 3.3 SegmentDumper：转储器

`SegmentDumper` 负责将 MemSegment 转储到磁盘，定义在 `framework/SegmentDumper.h` 中：

```cpp
// framework/SegmentDumper.h
class SegmentDumper : public SegmentDumpable
{
public:
    SegmentDumper(const std::string& tabletName, 
                  const std::shared_ptr<MemSegment>& segment,
                  int64_t dumpExpandMemSize,
                  std::shared_ptr<kmonitor::MetricsReporter> metricsReporter)
        : _tabletName(tabletName)
        , _dumpingSegment(segment)
        , _dumpExpandMemSize(dumpExpandMemSize)
    {
        // 设置 Segment 状态为 DUMPING
        _dumpingSegment->SetSegmentStatus(Segment::SegmentStatus::ST_DUMPING);
    }
    
    // 执行转储
    virtual Status Dump() = 0;
    
    // 获取转储的 SegmentMeta
    virtual std::pair<Status, SegmentMeta> GetDumpedSegmentMeta() = 0;
};
```

**转储流程**：

![SegmentDumper 转储流程：从创建到完成的完整过程](/images/diagrams/indexlib-flush-dumper-flow.svg)

1. **创建 Dumper**：`CreateSegmentDumper()` 创建转储器
2. **设置状态**：将 MemSegment 状态设置为 `ST_DUMPING`
3. **执行转储**：调用 `Dump()` 将内存数据写入磁盘
4. **创建 DiskSegment**：转储完成后创建 DiskSegment
5. **更新状态**：MemSegment 状态变为 `ST_BUILT`（实际已被 DiskSegment 替代）

### 3.4 异步转储机制

转储是异步的，不会阻塞新的写入。关键设计：

![异步转储机制：不阻塞写入，提高吞吐量](/images/diagrams/indexlib-flush-async-dump.svg)

**异步转储的优势**：
- **不阻塞写入**：转储过程中可以创建新的 MemSegment 继续接收写入
- **提高吞吐量**：写入和转储可以并行进行
- **资源控制**：通过 `DumpControl` 控制转储任务的并发度

### 3.5 转储的内存成本

转储需要额外的内存空间，通过 `DumpExpandMemSize` 控制：

![转储内存成本：DumpExpandMemSize 的控制机制](/images/diagrams/indexlib-flush-memory-cost.svg)

**内存成本控制**：
- **估算转储内存**：`EstimateDumpMemUsed()` 估算转储所需内存
- **检查内存配额**：检查是否有足够的内存配额
- **控制转储并发**：通过内存配额控制转储任务的并发度

## 4. Seal：封存阶段

### 4.1 Seal 流程

Seal 阶段负责封存 Segment，标记为只读，不再接收新文档。让我们先通过图来理解 Seal 流程：

![Seal 流程：封存 Segment，标记为只读](/images/diagrams/indexlib-seal-process.svg)

Seal 流程包括以下步骤：

1. **封存 MemSegment**：调用 `MemSegment::Seal()` 封存当前构建中的 Segment
2. **标记为只读**：Segment 不再接收新文档
3. **触发转储**：如果 MemSegment 有数据，触发转储
4. **等待转储完成**：等待转储完成，创建 DiskSegment
5. **更新状态**：Segment 状态变为 `ST_BUILT`

### 4.2 MemSegment::Seal()

`MemSegment::Seal()` 的实现：

```cpp
// framework/MemSegment.h
class MemSegment : public Segment
{
public:
    // 封存：标记为只读，不再接收新文档
    virtual void Seal() = 0;
};
```

**Seal 的作用**：
- **标记只读**：Segment 不再接收新文档
- **准备合并**：封存的 Segment 可以参与合并
- **保证一致性**：封存后 Segment 内容不再变化

### 4.3 Seal 的使用场景

Seal 通常在以下场景使用：

![Seal 使用场景：合并前、版本提交前等](/images/diagrams/indexlib-seal-scenarios.svg)

**使用场景**：
- **合并前**：合并前需要封存所有待合并的 Segment
- **版本提交前**：版本提交前需要封存所有 Segment
- **Schema 变更前**：Schema 变更前需要封存当前 Segment

## 5. Commit：提交版本阶段

### 5.1 Commit 流程

Commit 阶段负责提交新版本，更新 Version，持久化到磁盘。让我们先通过图来理解 Commit 流程：

![Commit 流程：从版本准备到持久化的完整过程](/images/diagrams/indexlib-commit-process.svg)

Commit 流程包括以下步骤：

1. **检查提交条件**：判断是否需要提交（有新的 Segment、有数据变更等）
2. **准备版本信息**：准备新版本的 Segment 列表、Locator 等
3. **创建 Fence**：创建 Fence，保证原子性
4. **持久化 Version**：将 Version 写入磁盘
5. **更新 TabletData**：更新 TabletData 的 Version
6. **清理旧版本**：清理不再需要的旧版本文件

### 5.2 VersionCommitter：版本提交器

`VersionCommitter` 负责版本提交，定义在 `framework/VersionCommitter.h` 中：

```cpp
// framework/VersionCommitter.h
class VersionCommitter
{
public:
    // 提交版本
    static std::pair<Status, VersionMeta> Commit(
        const std::shared_ptr<TabletData>& tabletData,
        const std::shared_ptr<config::ITabletSchema>& schema,
        const CommitOptions& commitOptions);
};
```

**Commit 的关键步骤**：

![VersionCommitter 提交流程：从准备到持久化的详细步骤](/images/diagrams/indexlib-commit-committer-flow.svg)

1. **准备版本信息**：收集所有已构建的 Segment，准备 Locator
2. **创建 Fence**：创建 Fence 目录，保证原子性
3. **写入 Version**：将 Version 写入 Fence 目录
4. **原子切换**：原子性地将 Fence 目录切换为正式版本目录
5. **更新 TabletData**：更新 TabletData 的 Version

### 5.3 Fence：原子性保证

Fence 机制保证版本提交的原子性：

![Fence 机制：保证版本提交的原子性](/images/diagrams/indexlib-commit-fence.svg)

**Fence 机制**：
- **创建 Fence 目录**：在提交前创建临时目录（Fence）
- **写入 Version**：将 Version 写入 Fence 目录
- **原子切换**：原子性地将 Fence 目录重命名为正式版本目录
- **保证原子性**：要么全部成功，要么全部失败

### 5.4 CommitOptions：提交选项

`CommitOptions` 控制提交行为，定义在 `framework/CommitOptions.h` 中：

```cpp
// framework/CommitOptions.h
struct CommitOptions
{
    // 是否强制提交（即使没有数据变更）
    bool forceCommit = false;
    
    // 提交的描述信息
    std::string commitMessage;
    
    // 是否等待转储完成
    bool waitDumpFinish = true;
    
    // 是否清理旧版本
    bool cleanVersion = false;
    
    // 保留的版本列表
    std::vector<versionid_t> reservedVersions;
};
```

**提交选项的作用**：
- **forceCommit**：强制提交，即使没有数据变更
- **waitDumpFinish**：等待转储完成后再提交
- **cleanVersion**：清理不再需要的旧版本文件

### 5.5 版本演进

每次 Commit 都会创建新版本，版本号递增：

![版本演进：从 V1 到 V2 的版本变化](/images/diagrams/indexlib-commit-version-evolution.svg)

**版本演进示例**：
- **V1**：包含 Segment [1, 2]，Locator 记录处理到 timestamp=100
- **V2**：新增 Segment 3，Locator 更新到 timestamp=200
- **V3**：Segment 1 和 2 合并为 Segment 4，Locator 更新到 timestamp=300

## 6. 完整构建流程示例

### 6.1 实时写入场景

在实时写入场景中，完整的构建流程：

![实时写入场景：从 Build 到 Commit 的完整流程](/images/diagrams/indexlib-build-realtime-scenario.svg)

**流程示例**：
1. **持续 Build**：文档持续写入 MemSegment
2. **定期 Flush**：MemSegment 达到阈值后触发 Flush，转储为 DiskSegment
3. **创建新 Segment**：创建新的 MemSegment 继续接收写入
4. **定期 Seal**：定期 Seal 旧的 Segment，准备合并
5. **定期 Commit**：定期 Commit，更新 Version

### 6.2 批量构建场景

在批量构建场景中，完整的构建流程：

![批量构建场景：一次性构建大量文档](/images/diagrams/indexlib-build-batch-scenario.svg)

**流程示例**：
1. **批量 Build**：一次性构建大量文档
2. **Flush**：构建完成后 Flush，转储为 DiskSegment
3. **Seal**：Seal 所有 Segment
4. **Commit**：Commit 最终版本

## 7. 构建流程的关键设计

### 7.1 异步与并发

IndexLib 的构建流程支持异步和并发：

![构建流程的异步与并发：提高吞吐量](/images/diagrams/indexlib-build-async-concurrent.svg)

**异步与并发设计**：
- **异步转储**：转储是异步的，不阻塞写入
- **并发构建**：支持多线程构建（NormalTabletParallelBuilder）
- **并发转储**：支持多个 Segment 并发转储

### 7.2 内存管理

构建流程需要严格控制内存使用：

![构建流程的内存管理：估算、评估、控制](/images/diagrams/indexlib-build-memory-management.svg)

**内存管理机制**：
- **内存估算**：构建前估算所需内存
- **内存评估**：构建过程中评估实际内存使用
- **内存控制**：通过 `MemoryQuotaController` 控制内存上限
- **触发转储**：达到阈值时触发转储，释放内存

### 7.3 错误处理

构建流程需要完善的错误处理：

![构建流程的错误处理：重试、回滚等](/images/diagrams/indexlib-build-error-handling.svg)

**错误处理机制**：
- **重试机制**：构建失败时可以重试
- **回滚机制**：转储失败时可以回滚
- **原子性保证**：通过 Fence 保证版本提交的原子性

## 8. 性能优化

### 8.1 构建性能优化

构建性能优化的关键点：

![构建性能优化：批量写入、并行构建等](/images/diagrams/indexlib-build-performance-optimization.svg)

**优化策略**：
- **批量写入**：支持批量写入文档，减少调用开销
- **并行构建**：支持多线程构建，提高构建速度
- **内存优化**：优化内存使用，减少内存分配开销

### 8.2 转储性能优化

转储性能优化的关键点：

![转储性能优化：异步转储、并发转储等](/images/diagrams/indexlib-flush-performance-optimization.svg)

**优化策略**：
- **异步转储**：转储不阻塞写入，提高吞吐量
- **并发转储**：支持多个 Segment 并发转储
- **IO 优化**：优化 IO 操作，减少 IO 开销

## 9. 小结

索引构建流程是 IndexLib 的核心功能，包括 Build、Flush、Seal、Commit 四个阶段。通过本文的深入解析，我们了解到：

**关键要点**：
- **Build**：接收文档批次，构建索引到内存（MemSegment）
- **Flush**：将内存数据刷新到磁盘，创建 DiskSegment
- **Seal**：封存 Segment，标记为只读，准备合并
- **Commit**：提交新版本，更新 Version，持久化到磁盘
- **异步转储**：转储是异步的，不阻塞写入，提高吞吐量
- **内存控制**：通过内存估算、评估、控制机制，避免内存溢出
- **原子性保证**：通过 Fence 机制保证版本提交的原子性

理解索引构建流程，是掌握 IndexLib 索引机制的关键。在下一篇文章中，我们将深入介绍查询流程的实现细节。
