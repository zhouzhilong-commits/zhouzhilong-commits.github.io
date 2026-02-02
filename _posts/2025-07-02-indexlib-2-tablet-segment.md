---
layout: single
title: "IndexLib（2）：Tablet 与 Segment：索引的组织方式"
series: indexlib
permalink: /indexlib-2-tablet-segment/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-07-02
---

在上一篇文章中，我们介绍了 IndexLib 的整体架构和核心概念。本文将继续深入，详细解析 Tablet 和 Segment 的组织方式，这是理解 IndexLib 索引机制的关键。

![Tablet 与 Segment 的组织关系：一个 Tablet 包含多个 Segment](/images/diagrams/indexlib-tablet-segment-organization.svg)

## 1. Tablet 与 Segment 的关系

### 1.1 整体组织架构

Tablet 是索引表的完整抽象，而 Segment 是索引的基本存储单元。一个 Tablet 包含多个 Segment，这些 Segment 按照时间顺序组织，共同构成完整的索引。

通过阅读源码，我们可以看到 Tablet 和 Segment 的关系定义在 `framework/TabletData.h` 中：

```cpp
// framework/TabletData.h
class TabletData : private autil::NoCopyable
{
private:
    Version _onDiskVersion;                               // 磁盘版本
    std::vector<std::shared_ptr<Segment>> _segments;     // Segment 列表（有序）
    std::shared_ptr<ResourceMap> _resourceMap;           // 共享资源
};
```

**关键设计**：
- **有序列表**：`_segments` 是一个有序的 Segment 列表，按照 SegmentId 排序
- **版本管理**：`_onDiskVersion` 记录哪些 Segment 已持久化
- **共享资源**：多个 Segment 共享 `ResourceMap`（内存池、缓存等）

### 1.2 Segment 的 ID 分配机制

Segment 的 ID 分配有特殊的规则，定义在 `framework/Segment.h` 中：

```cpp
// framework/Segment.h
class Segment {
public:
    // Segment ID 的掩码定义
    static constexpr segmentid_t RT_SEGMENT_ID_MASK = (segmentid_t)0x1 << 30;      // 实时 Segment
    static constexpr segmentid_t MERGED_SEGMENT_ID_MASK = (segmentid_t)0x0;         // 合并 Segment
    static constexpr segmentid_t PUBLIC_SEGMENT_ID_MASK = (segmentid_t)0x1 << 29;   // 公共 Segment
    static constexpr segmentid_t PRIVATE_SEGMENT_ID_MASK = (segmentid_t)0x1 << 30; // 私有 Segment

    // 判断 Segment 类型
    static bool IsRtSegmentId(segmentid_t segId) { 
        return (segId & RT_SEGMENT_ID_MASK) > 0; 
    }
    
    static bool IsMergedSegmentId(segmentid_t segId) {
        return segId != INVALID_SEGMENTID && 
               (segId & (PUBLIC_SEGMENT_ID_MASK | PRIVATE_SEGMENT_ID_MASK)) == 0;
    }
};
```

**Segment ID 的分类**：

![Segment ID 分类：实时 Segment、合并 Segment 的 ID 分配规则](/images/diagrams/indexlib-segment-id-allocation.svg)

- **实时 Segment（RT Segment）**：ID 的第 30 位为 1，用于实时写入
- **合并 Segment（Merged Segment）**：ID 的第 29、30 位都为 0，用于合并后的 Segment
- **公共/私有 Segment**：通过第 29 位区分

## 2. Segment 的元数据：SegmentMeta 与 SegmentInfo

### 2.1 SegmentMeta：Segment 的元数据

`SegmentMeta` 记录 Segment 的元数据信息，定义在 `framework/SegmentMeta.h` 中：

```cpp
// framework/SegmentMeta.h
struct SegmentMeta {
    segmentid_t segmentId;                                    // Segment ID
    std::shared_ptr<indexlib::file_system::Directory> segmentDir;  // Segment 目录
    std::shared_ptr<SegmentInfo> segmentInfo;                  // Segment 信息
    std::shared_ptr<indexlib::framework::SegmentMetrics> segmentMetrics;  // Segment 指标
    std::shared_ptr<config::ITabletSchema> schema;            // Schema
    std::string lifecycle;                                     // 生命周期标签
};
```

**SegmentMeta 的组成**：

![SegmentMeta 的组成：包含 SegmentId、Directory、SegmentInfo 等](/images/diagrams/indexlib-segment-meta-structure.svg)

- **segmentId**：Segment 的唯一标识
- **segmentDir**：Segment 的目录，用于文件操作
- **segmentInfo**：Segment 的详细信息（文档数、Locator 等）
- **schema**：Segment 使用的 Schema（支持 Schema 演进）
- **lifecycle**：生命周期标签，用于数据管理

### 2.2 SegmentInfo：Segment 的详细信息

`SegmentInfo` 记录 Segment 的详细信息，定义在 `framework/SegmentInfo.h` 中：

```cpp
// framework/SegmentInfo.h
class SegmentInfo : public autil::legacy::Jsonizable
{
public:
    // 基本信息
    volatile uint64_t docCount = 0;              // 文档数量
    int64_t timestamp = INVALID_TIMESTAMP;      // 时间戳
    schemaid_t schemaId = DEFAULT_SCHEMAID;     // Schema ID
    
    // Locator 信息
    Locator GetLocator() const;
    void SetLocator(const Locator& locator);
    
    // 分片信息
    uint32_t shardId = INVALID_SHARDING_ID;      // 分片 ID
    uint32_t shardCount = 1;                    // 分片数量
    
    // 其他信息
    bool mergedSegment = false;                 // 是否合并 Segment
    uint32_t maxTTL = 0;                        // 最大 TTL
    std::map<std::string, std::string> descriptions;  // 描述信息
};
```

**SegmentInfo 的关键字段**：

![SegmentInfo 的关键字段：docCount、Locator、shardId 等](/images/diagrams/indexlib-segment-info-fields.svg)

- **docCount**：Segment 中的文档数量，用于 DocId 映射
- **Locator**：数据位置信息，用于增量更新
- **shardId/shardCount**：分片信息，支持分片存储
- **mergedSegment**：标识是否为合并 Segment

## 3. DocId 映射机制

### 3.1 全局 DocId 与局部 DocId

IndexLib 使用两级 DocId 机制：
- **全局 DocId**：在整个 Tablet 范围内唯一的文档 ID
- **局部 DocId**：在单个 Segment 内的文档 ID（从 0 开始）

**DocId 映射关系**：

![DocId 映射：全局 DocId 与局部 DocId 的转换关系](/images/diagrams/indexlib-docid-mapping.svg)

从代码中可以看到，`TabletData` 提供了获取 Segment 及其基础 DocId 的方法：

```cpp
// framework/TabletData.h
class TabletData {
public:
    // 获取 Segment 及其基础 DocId
    // 返回：(Segment 指针, 基础 DocId)
    std::pair<SegmentPtr, docid64_t> GetSegmentWithBaseDocid(segmentid_t segmentId);
};
```

**DocId 计算逻辑**（通过代码分析）：

```cpp
// 伪代码：计算全局 DocId
docid64_t globalDocId = baseDocId + localDocId;

// 其中：
// - baseDocId：前面所有 Segment 的文档数之和
// - localDocId：当前 Segment 内的局部 DocId
```

### 3.2 BaseDocId 的计算

BaseDocId 是 Segment 的全局 DocId 起始值，等于前面所有 Segment 的文档数之和：

![BaseDocId 计算：前面所有 Segment 的文档数之和](/images/diagrams/indexlib-basedocid-calculation.svg)

**计算示例**：
- Segment 1：docCount=1000，baseDocId=0
- Segment 2：docCount=2000，baseDocId=1000
- Segment 3：docCount=1500，baseDocId=3000

**代码实现逻辑**（通过阅读源码理解）：

```cpp
// TabletData 内部维护 Segment 列表
// 计算 baseDocId 时，遍历前面的 Segment，累加 docCount
docid64_t baseDocId = 0;
for (auto& seg : _segments) {
    if (seg->GetSegmentId() == segmentId) {
        break;
    }
    baseDocId += seg->GetDocCount();
}
```

## 4. TabletData 的 Segment 管理

### 4.1 Segment 的添加与移除

TabletData 通过 `Init()` 方法初始化 Segment 列表：

```cpp
// framework/TabletData.h
class TabletData {
public:
    // 初始化：设置版本和 Segment 列表
    Status Init(Version onDiskVersion, 
                std::vector<SegmentPtr> segments,
                const std::shared_ptr<ResourceMap>& resourceMap);
};
```

**Segment 列表的维护**：

![TabletData Segment 列表维护：添加、移除、更新](/images/diagrams/indexlib-tabletdata-segment-management.svg)

- **初始化**：通过 `Init()` 设置初始 Segment 列表
- **添加**：新 Segment 通过 `TabletWriter` 创建后添加到列表
- **移除**：合并后，旧 Segment 从列表中移除
- **更新**：`Reopen()` 时更新 Segment 列表

### 4.2 Slice 机制：按状态筛选 Segment

`Slice` 是 TabletData 提供的 Segment 视图机制，可以按状态筛选 Segment：

```cpp
// framework/TabletData.h
class TabletData {
public:
    class Slice {
        // 提供迭代器，可以遍历筛选后的 Segment
        auto begin() { return _cBegin; }
        auto end() { return _cEnd; }
        auto rbegin() { return _cRbegin; }
        auto rend() { return _cRend; }
    };
    
    // 创建 Slice：按状态筛选
    Slice CreateSlice(Segment::SegmentStatus segmentStatus) const;
};
```

**Slice 的使用场景**：

![TabletData Slice 使用场景：查询、写入、合并时的 Segment 筛选](/images/diagrams/indexlib-tabletdata-slice-usage.svg)

1. **查询时**：`CreateSlice(ST_BUILT)` 获取所有已构建的 Segment
2. **写入时**：`CreateSlice(ST_BUILDING)` 获取构建中的 Segment
3. **合并时**：`CreateSlice(ST_BUILT)` 获取需要合并的 Segment

## 5. MemSegment 的实现细节

### 5.1 NormalMemSegment 的构建流程

通过阅读 `table/normal_table/NormalMemSegment.h`，我们可以看到 NormalMemSegment 的实现：

```cpp
// table/normal_table/NormalMemSegment.h
class NormalMemSegment : public plain::PlainMemSegment
{
public:
    NormalMemSegment(const config::TabletOptions* options, 
                    const std::shared_ptr<config::ITabletSchema>& schema,
                    const framework::SegmentMeta& segmentMeta);
    
protected:
    // 创建转储参数
    std::pair<Status, std::shared_ptr<framework::DumpParams>> CreateDumpParams() override;
    
    // 计算转储内存成本
    void CalcMemCostInCreateDumpParams() override;
};
```

**MemSegment 的构建流程**：

![MemSegment 构建流程：从 Open 到 Build 的完整过程](/images/diagrams/indexlib-memsegment-build-flow.svg)

1. **Open**：初始化构建资源，创建 Indexer
2. **Build**：接收文档批次，写入各个 Indexer
3. **NeedDump**：检查是否达到转储条件
4. **CreateDumpParams**：创建转储参数，计算内存成本

### 5.2 MemSegment 的内存管理

MemSegment 在内存中构建索引，需要严格控制内存使用。关键代码（`table/plain/PlainMemSegment.h`）：

```cpp
class PlainMemSegment : public MemSegment {
public:
    // 估算内存使用
    std::pair<Status, size_t> EstimateMemUsed(
        const std::shared_ptr<config::ITabletSchema>& schema) override;
    
    // 评估当前内存使用
    size_t EvaluateCurrentMemUsed() override;
};
```

**内存管理机制**：

![MemSegment 内存管理：估算、评估、控制内存使用](/images/diagrams/indexlib-memsegment-memory-management.svg)

- **估算**：`EstimateMemUsed()` 估算构建所需内存
- **评估**：`EvaluateCurrentMemUsed()` 评估当前实际内存使用
- **控制**：通过 `MemoryQuotaController` 控制内存上限
- **转储**：达到阈值时触发转储，释放内存

## 6. DiskSegment 的实现细节

### 6.1 NormalDiskSegment 的加载流程

通过阅读 `table/normal_table/NormalDiskSegment.h`，我们可以看到 NormalDiskSegment 的实现：

```cpp
// table/normal_table/NormalDiskSegment.h
class NormalDiskSegment : public plain::PlainDiskSegment
{
public:
    NormalDiskSegment(const std::shared_ptr<config::ITabletSchema>& schema,
                     const framework::SegmentMeta& segmentMeta, 
                     const framework::BuildResource& buildResource);
    
    // 估算内存使用
    std::pair<Status, size_t> EstimateMemUsed(
        const std::shared_ptr<config::ITabletSchema>& schema) override;

private:
    // 打开 Indexer
    std::pair<Status, std::vector<plain::DiskIndexerItem>>
    OpenIndexer(const std::shared_ptr<config::IIndexConfig>& indexConfig) override;
};
```

**DiskSegment 的加载流程**：

![DiskSegment 加载流程：从 Open 到 GetIndexer 的完整过程](/images/diagrams/indexlib-disksegment-load-flow.svg)

1. **Open**：打开 Segment 目录，读取 SegmentInfo
2. **OpenIndexer**：按需打开各个 Indexer（NORMAL 模式立即打开，LAZY 模式按需打开）
3. **GetIndexer**：查询时获取 Indexer，LAZY 模式下此时才加载
4. **Reopen**：Schema 变更时重新打开

### 6.2 DiskSegment 的按需加载

DiskSegment 支持按需加载，通过 `GetIndexer()` 方法实现：

```cpp
// framework/Segment.h
class Segment {
public:
    // 获取 Indexer（LAZY 模式下按需加载）
    virtual std::pair<Status, std::shared_ptr<indexlibv2::index::IIndexer>> 
        GetIndexer(const std::string& type, const std::string& indexName) {
        return std::make_pair(Status::NotFound(), nullptr);
    }
};
```

**按需加载的优势**：

![DiskSegment 按需加载：减少内存占用，提高启动速度](/images/diagrams/indexlib-disksegment-lazy-loading.svg)

- **减少内存占用**：只加载查询需要的索引
- **提高启动速度**：不需要等待所有索引加载完成
- **灵活查询**：支持部分索引查询场景

## 7. TabletWriter 与 Segment 的交互

### 7.1 TabletWriter 的构建流程

通过阅读 `table/normal_table/NormalTabletWriter.h`，我们可以看到 TabletWriter 的实现：

```cpp
// table/normal_table/NormalTabletWriter.h
class NormalTabletWriter : public table::CommonTabletWriter
{
public:
    // 打开：初始化 TabletData 和构建资源
    Status Open(const std::shared_ptr<framework::TabletData>& tabletData, 
                const framework::BuildResource& buildResource,
                const framework::OpenOptions& openOptions) override;
    
    // 构建：接收文档批次并写入
    Status Build(const std::shared_ptr<document::IDocumentBatch>& batch) override;
    
    // 创建 SegmentDumper：准备转储
    std::unique_ptr<framework::SegmentDumper> CreateSegmentDumper() override;

private:
    std::shared_ptr<NormalMemSegment> _normalBuildingSegment;  // 当前构建中的 Segment
    docid_t _buildingSegmentBaseDocId;                         // 构建 Segment 的基础 DocId
};
```

**TabletWriter 与 Segment 的交互流程**：

![TabletWriter 与 Segment 交互：从 Open 到 Build 的完整流程](/images/diagrams/indexlib-tabletwriter-segment-interaction.svg)

1. **Open**：初始化 TabletData，创建或获取 MemSegment
2. **Build**：将文档写入 `_normalBuildingSegment`
3. **NeedDump**：检查 MemSegment 是否需要转储
4. **CreateSegmentDumper**：创建转储器，准备转储
5. **Dump**：将 MemSegment 转储为 DiskSegment
6. **Reopen**：更新 TabletData，添加新的 DiskSegment

### 7.2 文档的 DocId 分配

TabletWriter 在构建时需要为文档分配 DocId。关键代码：

```cpp
// table/normal_table/NormalTabletWriter.h
class NormalTabletWriter {
private:
    // 分发 DocId：为文档分配 DocId
    void DispatchDocIds(document::IDocumentBatch* batch);
    
    docid_t _buildingSegmentBaseDocId;  // 当前构建 Segment 的基础 DocId
};
```

**DocId 分配机制**：

![文档 DocId 分配：全局 DocId 的计算和分配](/images/diagrams/indexlib-docid-allocation.svg)

- **BaseDocId**：当前 MemSegment 的全局 DocId 起始值
- **LocalDocId**：在 MemSegment 内的局部 DocId（从 0 开始递增）
- **GlobalDocId**：`baseDocId + localDocId`

## 8. Segment 的转储机制

### 8.1 SegmentDumper：转储器

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

![Segment 转储流程：从 MemSegment 到 DiskSegment 的完整过程](/images/diagrams/indexlib-segment-dump-flow.svg)

1. **创建 Dumper**：`CreateSegmentDumper()` 创建转储器
2. **设置状态**：将 MemSegment 状态设置为 `ST_DUMPING`
3. **执行转储**：调用 `Dump()` 将内存数据写入磁盘
4. **创建 DiskSegment**：转储完成后创建 DiskSegment
5. **更新状态**：MemSegment 状态变为 `ST_BUILT`（实际已被 DiskSegment 替代）

### 8.2 转储的异步机制

转储是异步的，不会阻塞新的写入。关键设计：

```cpp
// framework/SegmentDumper.h
class DumpControl {
public:
    // 控制转储任务的执行
    std::tuple<uint32_t, uint32_t> StartTask();
    std::tuple<uint32_t, uint32_t> Iterate(Status& taskStatus);
    uint32_t ExitTask(const bool isCoordinator);

private:
    std::atomic<uint32_t> _finishCount = 0;  // 完成的任务数
    uint32_t _totalCount;                     // 总任务数
    std::mutex _dumpMutex;                    // 转储互斥锁
    std::condition_variable _dumpCv;          // 转储条件变量
};
```

**异步转储的优势**：

![异步转储机制：不阻塞写入，提高吞吐量](/images/diagrams/indexlib-async-dump.svg)

- **不阻塞写入**：转储过程中可以创建新的 MemSegment 继续接收写入
- **提高吞吐量**：写入和转储可以并行进行
- **资源控制**：通过 `DumpControl` 控制转储任务的并发度

## 9. Segment 的查询机制

### 9.1 多 Segment 并行查询

查询时需要遍历多个 Segment，可以并行查询以提高性能：

![多 Segment 并行查询：提高查询性能](/images/diagrams/indexlib-multi-segment-query.svg)

**查询流程**：
1. **获取 Segment 列表**：`TabletData->CreateSlice(ST_BUILT)` 获取所有已构建的 Segment
2. **并行查询**：对每个 Segment 的 Indexer 进行查询（如果支持并行）
3. **合并结果**：将各 Segment 的查询结果合并（去重、排序等）

### 9.2 DocId 转换

查询时需要将全局 DocId 转换为局部 DocId：

```cpp
// 伪代码：全局 DocId 转局部 DocId
for (auto& seg : segments) {
    docid64_t baseDocId = GetBaseDocId(seg);
    if (globalDocId >= baseDocId && globalDocId < baseDocId + seg->GetDocCount()) {
        docid_t localDocId = globalDocId - baseDocId;
        // 在 Segment 内查询
        return seg->GetIndexer()->Get(localDocId);
    }
}
```

**DocId 转换流程**：

![DocId 转换：全局 DocId 到局部 DocId 的转换过程](/images/diagrams/indexlib-docid-conversion.svg)

1. **定位 Segment**：根据全局 DocId 找到对应的 Segment
2. **计算 BaseDocId**：计算该 Segment 的基础 DocId
3. **转换为局部 DocId**：`localDocId = globalDocId - baseDocId`
4. **Segment 内查询**：使用局部 DocId 在 Segment 内查询

## 10. Segment 的生命周期管理

### 10.1 Segment 的创建

Segment 的创建通过 `ITabletFactory` 实现：

```cpp
// framework/ITabletFactory.h
class ITabletFactory {
public:
    // 创建 MemSegment
    virtual std::unique_ptr<MemSegment> CreateMemSegment(
        const SegmentMeta& segmentMeta) = 0;
    
    // 创建 DiskSegment
    virtual std::unique_ptr<DiskSegment> CreateDiskSegment(
        const SegmentMeta& segmentMeta,
        const framework::BuildResource& buildResource) = 0;
};
```

**Segment 创建流程**：

![Segment 创建流程：从 Factory 到 TabletData 的完整过程](/images/diagrams/indexlib-segment-creation.svg)

1. **创建 SegmentMeta**：设置 SegmentId、Directory、Schema 等
2. **调用 Factory**：通过 `ITabletFactory` 创建 Segment
3. **初始化 Segment**：调用 `Open()` 初始化
4. **添加到 TabletData**：将 Segment 添加到 TabletData 的 Segment 列表

### 10.2 Segment 的销毁

Segment 的销毁通过智能指针自动管理：

```cpp
// Segment 使用 shared_ptr 管理
using SegmentPtr = std::shared_ptr<Segment>;

// 当 Segment 不再被引用时，自动析构
// 析构时会：
// 1. 释放内存资源（MemSegment）
// 2. 关闭文件句柄（DiskSegment）
// 3. 清理 Indexer
```

**Segment 销毁时机**：

![Segment 销毁时机：合并后、版本清理时自动销毁](/images/diagrams/indexlib-segment-destruction.svg)

- **合并后**：合并后的旧 Segment 不再被引用，自动销毁
- **版本清理**：清理旧版本时，旧 Segment 被销毁
- **资源回收**：通过 `ReclaimSegmentResource()` 主动回收资源

## 11. 实际应用场景

### 11.1 实时写入场景

在实时写入场景中，Tablet 和 Segment 的组织方式：

![实时写入场景：MemSegment 接收写入，定期转储为 DiskSegment](/images/diagrams/indexlib-realtime-write-scenario.svg)

1. **持续写入**：文档持续写入 MemSegment
2. **定期转储**：MemSegment 达到阈值后转储为 DiskSegment
3. **新 Segment**：创建新的 MemSegment 继续接收写入
4. **版本提交**：定期 Commit，更新 Version

### 11.2 查询场景

在查询场景中，需要遍历多个 Segment：

![查询场景：遍历多个 Segment，合并查询结果](/images/diagrams/indexlib-query-scenario.svg)

1. **获取 Segment 列表**：从 TabletData 获取所有已构建的 Segment
2. **并行查询**：对多个 Segment 进行并行查询
3. **结果合并**：合并各 Segment 的查询结果
4. **DocId 转换**：将局部 DocId 转换为全局 DocId

## 12. 小结

Tablet 和 Segment 的组织方式是 IndexLib 索引机制的核心。通过本文的深入解析，我们了解到：

**关键要点**：
- **Tablet 管理多个 Segment**：通过 TabletData 管理有序的 Segment 列表
- **Segment ID 分配**：通过掩码区分不同类型的 Segment（实时、合并等）
- **DocId 映射**：使用两级 DocId 机制（全局 DocId = baseDocId + localDocId）
- **SegmentMeta 和 SegmentInfo**：记录 Segment 的元数据和详细信息
- **MemSegment 和 DiskSegment**：内存段用于实时写入，磁盘段用于持久化存储
- **转储机制**：MemSegment 转储为 DiskSegment 是异步的，不阻塞写入
- **查询机制**：查询时遍历多个 Segment，可以并行查询提高性能
- **生命周期管理**：通过智能指针自动管理 Segment 的生命周期

理解 Tablet 和 Segment 的组织方式，是掌握 IndexLib 索引构建和查询机制的基础。在下一篇文章中，我们将深入介绍索引构建的完整流程。
