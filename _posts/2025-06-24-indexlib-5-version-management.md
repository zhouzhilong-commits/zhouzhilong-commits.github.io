---
layout: single
title: "IndexLib（5）：版本管理与增量更新"
series: indexlib
permalink: /indexlib-5-version-management/
tags: [IndexLib, 搜索引擎, 存储]
date: 2025-06-24
---

在上一篇文章中，我们深入了解了查询流程的实现。本文将继续深入，详细解析版本管理和增量更新的机制，这是理解 IndexLib 如何管理索引版本和实现增量更新的关键。

版本管理与增量更新概览：Version 与 Locator 的协同工作：

```mermaid
flowchart LR
    subgraph Input["数据输入"]
        A[数据源<br/>DataSource]
        B[文档流<br/>Document Stream]
        A --> B
    end
    
    subgraph Version["版本管理"]
        C[Version<br/>版本信息]
        D[VersionId<br/>版本号递增]
        E[Segments<br/>Segment列表]
        F[Schema演进<br/>SchemaId映射]
        C --> D
        C --> E
        C --> F
    end
    
    subgraph Locator["位置信息"]
        G[Locator<br/>数据处理位置]
        H[Timestamp<br/>时间戳]
        I[MultiProgress<br/>多进度信息]
        J[HashId<br/>分片标识]
        G --> H
        G --> I
        I --> J
    end
    
    subgraph Update["增量更新"]
        K[IsFasterThan<br/>比较判断]
        L[数据过滤<br/>过滤已处理]
        M[处理新数据<br/>构建索引]
        N[更新Locator<br/>记录进度]
        K --> L
        L --> M
        M --> N
    end
    
    subgraph Commit["版本提交"]
        O[VersionCommitter<br/>版本提交器]
        P[Fence机制<br/>原子性保证]
        Q[持久化<br/>写入磁盘]
        O --> P
        P --> Q
    end
    
    B --> G
    G --> K
    K --> C
    N --> C
    C --> O
    Q --> E
    
    style Input fill:#e3f2fd
    style Version fill:#fff3e0
    style Locator fill:#f3e5f5
    style Update fill:#e8f5e9
    style Commit fill:#fce4ec
```

## 1. 版本管理概览

### 1.1 版本管理的核心概念

IndexLib 的版本管理包括以下核心概念：

1. **Version**：版本信息，记录索引包含哪些 Segment
2. **Locator**：位置信息，记录数据处理的位置，用于增量更新
3. **版本演进**：每次 Commit 都会创建新版本，版本号递增
4. **增量更新**：通过 Locator 判断哪些数据已处理，避免重复处理

让我们先通过图来理解版本管理的整体架构：

版本管理架构：Version、Locator、Segment 的关系：

```mermaid
flowchart TD
    subgraph Version["Version 版本信息"]
        V1[VersionId<br/>版本号单调递增]
        V2[Segments<br/>Segment列表]
        V3[Locator<br/>位置信息]
        V4[Timestamp<br/>时间戳]
        V5[Sealed<br/>封存状态]
        V6[SchemaId<br/>Schema标识]
        V1 --> V2
        V1 --> V3
        V1 --> V4
        V1 --> V5
        V1 --> V6
    end
    
    subgraph Segment["Segment 索引段"]
        S1[SegmentId<br/>段标识]
        S2[SchemaId<br/>段Schema]
        S3[IndexFiles<br/>索引文件]
        S4[SegmentInfo<br/>段信息]
        S1 --> S2
        S1 --> S3
        S1 --> S4
    end
    
    subgraph Locator["Locator 位置信息"]
        L1[SourceId<br/>数据源标识]
        L2[Timestamp<br/>时间戳]
        L3[ConcurrentIdx<br/>并发索引]
        L4[HashId<br/>分片标识]
        L5[MultiProgress<br/>多进度信息]
        L1 --> L2
        L2 --> L3
        L3 --> L4
        L4 --> L5
    end
    
    subgraph Commit["版本提交"]
        C1[VersionCommitter<br/>提交器]
        C2[Fence目录<br/>临时目录]
        C3[原子切换<br/>重命名操作]
        C4[持久化<br/>写入磁盘]
        C1 --> C2
        C2 --> C3
        C3 --> C4
    end
    
    V2 -->|包含| S1
    V3 -->|包含| L1
    V1 -->|提交| C1
    C4 -->|更新| V1
    
    style Version fill:#e3f2fd
    style Segment fill:#fff3e0
    style Locator fill:#f3e5f5
    style Commit fill:#e8f5e9
```

### 1.2 版本管理的作用

版本管理在 IndexLib 中起到关键作用，是系统稳定性和数据一致性的基础。让我们通过类图来理解版本管理的整体架构：

```mermaid
classDiagram
    class Version {
        - versionid_t _versionId
        - vector_SegmentInVersion _segments
        - Locator _locator
        - int64_t _timestamp
        - bool _sealed
        + GetVersionId()
        + AddSegment()
        + SetLocator()
        + IncVersionId()
    }
    
    class Locator {
        - uint64_t _src
        - MultiProgress _multiProgress
        - string _userData
        + IsFasterThan()
        + Update()
        + Serialize()
    }
    
    class VersionCommitter {
        + Commit()
        + CreateFence()
        + WriteVersion()
    }
    
    class VersionLoader {
        + Load()
        + Validate()
    }
    
    Version --> Locator : 包含
    VersionCommitter --> Version : 创建
    VersionLoader --> Version : 加载
```

**版本管理的核心作用**：

- **版本控制**：记录索引的演进历史，支持版本回滚
  - **版本演进**：每次 Commit 创建新版本，版本号单调递增
  - **版本历史**：保留版本历史，支持查看和回滚到历史版本
  - **版本比较**：支持版本比较，判断版本之间的差异
  
- **增量更新**：通过 Locator 判断哪些数据已处理，实现增量更新
  - **数据定位**：通过 Locator 精确定位数据处理位置
  - **避免重复**：通过 Locator 比较避免重复处理数据
  - **进度追踪**：记录每个 HashId 的处理进度，支持分片处理
  
- **Schema 演进**：支持 Schema 变更，每个 Segment 记录自己的 SchemaId
  - **向后兼容**：新 Schema 向后兼容旧 Schema，旧 Segment 可以继续使用
  - **渐进式迁移**：新 Segment 使用新 Schema，旧 Segment 保持原样
  - **版本映射**：通过 SchemaVersionRoadMap 记录 Schema 版本映射
  
- **数据一致性**：保证数据不重复、不丢失，支持多数据源场景
  - **不重复保证**：通过 Locator 比较保证数据不重复处理
  - **不丢失保证**：通过 Locator 更新保证数据不丢失
  - **多数据源支持**：通过 `sourceIdx` 区分数据源，支持多数据源场景

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

Version 的结构：包含 VersionId、Segments、Locator 等关键信息：

```mermaid
flowchart TD
    subgraph Version["Version 对象"]
        V[Version<br/>版本信息]
    end
    
    subgraph Fields["核心字段"]
        F1[VersionId<br/>版本号<br/>单调递增]
        F2[Segments<br/>Segment列表<br/>vector SegmentInVersion]
        F3[Locator<br/>位置信息<br/>用于增量更新]
        F4[Timestamp<br/>时间戳<br/>版本创建时间]
        F5[Sealed<br/>封存状态<br/>是否封存]
        F6[SchemaId<br/>Schema标识<br/>当前Schema版本]
        F7[FenceName<br/>Fence名称<br/>临时目录名]
    end
    
    subgraph SegmentInVersion["SegmentInVersion 结构"]
        S1[SegmentId<br/>段标识<br/>INVALID_SEGMENTID]
        S2[SchemaId<br/>段Schema<br/>DEFAULT_SCHEMAID]
        S1 --> S2
    end
    
    V --> F1
    V --> F2
    V --> F3
    V --> F4
    V --> F5
    V --> F6
    V --> F7
    F2 -->|包含| S1
    
    style Version fill:#e3f2fd
    style Fields fill:#fff3e0
    style SegmentInVersion fill:#f3e5f5
```

- **VersionId**：版本号，单调递增，每次 Commit 时递增
- **Segments**：该版本包含的 Segment 列表，每个 Segment 记录自己的 SchemaId
- **Locator**：数据位置信息，用于增量更新
- **Timestamp**：时间戳，记录版本创建时间
- **Sealed**：是否封存，封存后不再接收新 Segment

### 2.2 Version 的演进

每次 Commit 都会创建新版本，版本号递增：

Version 演进：从 V1 到 V2 的版本变化：

```mermaid
flowchart LR
    subgraph V1["Version 1"]
        V1_ID[VersionId: 1]
        V1_SEG[Segments: 1, 2]
        V1_LOC[Locator: timestamp=100]
        V1_SCHEMA[SchemaId: 0]
        V1_ID --> V1_SEG
        V1_ID --> V1_LOC
        V1_ID --> V1_SCHEMA
    end
    
    subgraph Commit["Commit 操作"]
        C1[收集Segment]
        C2[更新Locator]
        C3[递增VersionId]
        C4[创建新版本]
        C1 --> C2
        C2 --> C3
        C3 --> C4
    end
    
    subgraph V2["Version 2"]
        V2_ID[VersionId: 2]
        V2_SEG[Segments: 1, 2, 3]
        V2_LOC[Locator: timestamp=200]
        V2_SCHEMA[SchemaId: 0]
        V2_ID --> V2_SEG
        V2_ID --> V2_LOC
        V2_ID --> V2_SCHEMA
    end
    
    subgraph V3["Version 3"]
        V3_ID[VersionId: 3]
        V3_SEG[Segments: 4]
        V3_LOC[Locator: timestamp=300]
        V3_SCHEMA[SchemaId: 0]
        V3_ID --> V3_SEG
        V3_ID --> V3_LOC
        V3_ID --> V3_SCHEMA
    end
    
    V1 -->|Commit| Commit
    Commit --> V2
    V2 -->|Merge| V3
    
    style V1 fill:#e3f2fd
    style Commit fill:#fff3e0
    style V2 fill:#f3e5f5
    style V3 fill:#e8f5e9
```

**版本演进示例**：
- **V1**：包含 Segment [1, 2]，Locator 记录处理到 timestamp=100
- **V2**：新增 Segment 3，Locator 更新到 timestamp=200
- **V3**：Segment 1 和 2 合并为 Segment 4，Locator 更新到 timestamp=300

**版本演进的关键设计**：

版本演进是 IndexLib 版本管理的核心机制。让我们通过序列图来理解版本演进的完整过程：

```mermaid
sequenceDiagram
    participant Writer as TabletWriter
    participant MemSeg as MemSegment
    participant DiskSeg as DiskSegment
    participant Version as Version
    participant VersionCommitter as VersionCommitter
    participant TabletData as TabletData
    
    Writer->>MemSeg: Build(documents)
    MemSeg-->>Writer: Success
    
    Writer->>MemSeg: NeedDump()?
    MemSeg-->>Writer: true
    
    Writer->>MemSeg: CreateSegmentDumpItems()
    MemSeg-->>Writer: DumpItems
    
    Writer->>DiskSeg: Dump(DumpItems)
    DiskSeg-->>Writer: Success
    
    Writer->>Version: AddSegment(segmentId, schemaId)
    Version->>Version: IncVersionId()
    Version-->>Writer: newVersionId
    
    Writer->>Version: SetLocator(locator)
    Version-->>Writer: Success
    
    Writer->>VersionCommitter: Commit(TabletData, Schema, Options)
    VersionCommitter->>VersionCommitter: CreateFence()
    VersionCommitter->>VersionCommitter: WriteVersion(Version)
    VersionCommitter->>VersionCommitter: AtomicSwitch()
    VersionCommitter-->>Writer: VersionMeta
    
    Writer->>TabletData: UpdateVersion(Version)
    TabletData-->>Writer: Success
```

**版本演进的关键设计**：

- **版本号递增**：每次 Commit 时 `VersionId` 自动递增，保证版本顺序
  - **单调性**：版本号严格单调递增，保证版本顺序
  - **原子性**：版本号递增是原子操作，避免并发问题
  - **持久化**：版本号持久化到磁盘，保证重启后继续递增
  
- **Schema 演进**：每个 Segment 记录自己的 `SchemaId`，支持 Schema 变更
  - **Segment SchemaId**：每个 Segment 在创建时记录自己的 SchemaId
  - **Schema 映射**：Version 维护 SchemaVersionRoadMap，记录 Schema 版本映射
  - **兼容性检查**：Schema 变更时检查兼容性，保证数据一致性
  
- **Locator 更新**：每次 Commit 时更新 Locator，记录最新的数据处理位置
  - **位置记录**：Locator 记录每个 HashId 的处理进度
  - **更新条件**：只有当新的 Locator 完全比当前 Locator 快时，才更新
  - **一致性保证**：保证 Locator 只向前推进，不会回退

### 2.3 Version 的持久化

Version 需要持久化到磁盘，通过 Fence 机制保证原子性：

Version 持久化：通过 Fence 机制保证原子性：

```mermaid
flowchart TD
    subgraph Prepare["准备阶段"]
        P1[PrepareVersion<br/>准备版本信息]
        P2[CollectSegments<br/>收集Segment列表]
        P3[PrepareLocator<br/>准备Locator信息]
        P1 --> P2
        P2 --> P3
    end
    
    subgraph Fence["Fence 机制"]
        F1[CreateFenceDirectory<br/>创建临时目录<br/>version.fence.timestamp]
        F2[WriteVersionFile<br/>写入版本文件<br/>序列化为JSON]
        F3[IncVersionId<br/>递增版本号]
        F4[AtomicRename<br/>原子重命名<br/>fence目录到正式目录]
        F1 --> F2
        F2 --> F3
        F3 --> F4
    end
    
    subgraph Persist["持久化"]
        PE1[序列化Version<br/>JSON格式]
        PE2[写入version文件<br/>version.0]
        PE3[写入元数据<br/>时间戳、Locator]
        PE1 --> PE2
        PE2 --> PE3
    end
    
    subgraph Update["更新内存"]
        U1[UpdateTabletData<br/>更新TabletData]
        U2[更新Version引用<br/>切换到新版本]
        U1 --> U2
    end
    
    subgraph Error["错误处理"]
        E1{提交失败?}
        E2[CleanupFence<br/>清理临时目录]
        E3[不影响已有版本<br/>保证一致性]
        E1 -->|是| E2
        E2 --> E3
    end
    
    P3 --> F1
    F2 --> PE1
    PE3 --> F3
    F4 --> U1
    U2 --> E1
    
    style Prepare fill:#e3f2fd
    style Fence fill:#fff3e0
    style Persist fill:#f3e5f5
    style Update fill:#e8f5e9
    style Error fill:#fce4ec
```

**持久化流程**：

Version 的持久化是版本管理的核心，通过 Fence 机制保证原子性。让我们通过序列图来理解完整的持久化流程：

```mermaid
sequenceDiagram
    participant Committer as VersionCommitter
    participant Version as Version
    participant FileSys as FileSystem
    participant TabletData as TabletData
    
    Committer->>Version: PrepareVersion()
    Version->>Version: CollectSegments()
    Version->>Version: PrepareLocator()
    Version-->>Committer: Version对象
    
    Committer->>FileSys: CreateFenceDirectory()
    FileSys-->>Committer: FencePath
    
    Committer->>FileSys: WriteVersionFile(Version, FencePath)
    FileSys->>FileSys: 序列化Version为JSON
    FileSys->>FileSys: 写入version文件
    FileSys-->>Committer: Success
    
    Committer->>Version: IncVersionId()
    Version-->>Committer: newVersionId
    
    Committer->>FileSys: AtomicRename(FencePath, VersionPath)
    FileSys-->>Committer: Success
    
    Committer->>TabletData: UpdateVersion(Version)
    TabletData-->>Committer: Success
    
    alt 提交失败
        Committer->>FileSys: CleanupFence(FencePath)
        FileSys-->>Committer: Success
    end
```

**持久化流程详解**：

1. **创建 Fence 目录**：在提交前创建临时目录（Fence）
   - **目录命名**：Fence 目录使用临时名称（如 `version.fence.1234567890`）
   - **目录隔离**：Fence 目录与正式版本目录隔离，避免冲突
   - **原子性准备**：Fence 目录为原子切换做准备
   
2. **写入 Version**：将 Version 写入 Fence 目录
   - **序列化**：将 Version 对象序列化为 JSON 格式
   - **文件写入**：将 JSON 写入版本文件（如 `version.0`）
   - **元数据写入**：写入版本元数据（时间戳、Locator 等）
   
3. **原子切换**：原子性地将 Fence 目录重命名为正式版本目录
   - **原子操作**：使用文件系统的原子重命名操作（`rename`）
   - **切换时机**：只有在所有文件写入成功后才切换
   - **失败处理**：如果切换失败，清理 Fence 目录，不影响已有版本
   
4. **保证原子性**：要么全部成功，要么全部失败
   - **事务性**：整个提交过程是事务性的，要么全部成功，要么全部失败
   - **错误恢复**：如果提交失败，可以清理 Fence 目录，不影响已有版本
   - **一致性保证**：保证版本文件的一致性，避免部分写入

**Fence 机制的设计优势**：

- **原子性**：通过原子重命名保证版本提交的原子性
- **性能**：Fence 机制不需要额外的锁，性能开销小
- **可靠性**：即使提交失败，也不会影响已有版本
- **简单性**：实现简单，易于理解和维护

### 2.4 Version 的加载

Version 的加载通过 `VersionLoader` 实现：

Version 加载：从磁盘加载版本信息：

```mermaid
flowchart TD
    subgraph Load["加载阶段"]
        L1[VersionLoader.Load<br/>加载版本]
        L2[读取版本文件<br/>version.0, version.1等]
        L3[解析JSON<br/>反序列化Version]
        L1 --> L2
        L2 --> L3
    end
    
    subgraph Validate["验证阶段"]
        V1[ValidateVersion<br/>验证版本有效性]
        V2[检查Segment存在性<br/>Segment文件是否存在]
        V3[检查Schema兼容性<br/>Schema版本映射]
        V4[检查Locator有效性<br/>Locator格式正确]
        V1 --> V2
        V2 --> V3
        V3 --> V4
    end
    
    subgraph Segment["加载Segment"]
        S1[根据Segment列表<br/>加载Segment]
        S2[OpenSegment<br/>打开Segment文件]
        S3[加载索引文件<br/>按需加载]
        S4[创建DiskSegment<br/>DiskSegment对象]
        S1 --> S2
        S2 --> S3
        S3 --> S4
    end
    
    subgraph Init["初始化TabletData"]
        I1[UpdateVersion<br/>更新Version]
        I2[设置Segment列表<br/>添加到TabletData]
        I3[初始化查询器<br/>准备查询]
        I1 --> I2
        I2 --> I3
    end
    
    L3 --> V1
    V4 --> S1
    S4 --> I1
    I3 --> End[完成加载]
    
    style Load fill:#e3f2fd
    style Validate fill:#fff3e0
    style Segment fill:#f3e5f5
    style Init fill:#e8f5e9
```

**加载流程**：
1. **读取版本文件**：从磁盘读取版本文件（version.0、version.1 等）
2. **解析 Version**：解析 JSON 格式的版本信息
3. **验证 Version**：验证版本的有效性（Segment 是否存在等）
4. **加载 Segment**：根据 Version 中的 Segment 列表加载 Segment

## 3. Locator：位置信息

### 3.1 Locator 的作用

Locator 是增量更新的核心，记录数据的位置信息：

Locator 的作用：记录数据处理位置，支持增量更新：

```mermaid
flowchart LR
    subgraph Role["Locator 核心作用"]
        R1[增量更新<br/>判断数据是否已处理]
        R2[数据一致性<br/>保证不重复不丢失]
        R3[进度追踪<br/>记录每个HashId进度]
        R4[并发控制<br/>处理时间戳相同情况]
    end
    
    subgraph Compare["比较机制"]
        C1[IsFasterThan<br/>比较两个Locator]
        C2[LCR_FULLY_FASTER<br/>完全更快]
        C3[LCR_SLOWER<br/>更慢]
        C4[LCR_PARTIAL_FASTER<br/>部分更快]
        C5[LCR_INVALID<br/>无效比较]
        C1 --> C2
        C1 --> C3
        C1 --> C4
        C1 --> C5
    end
    
    subgraph Update["更新机制"]
        U1[Update<br/>更新Locator]
        U2[条件检查<br/>新Locator必须更快]
        U3[更新MultiProgress<br/>记录最新进度]
        U4[保证一致性<br/>只向前推进]
        U1 --> U2
        U2 --> U3
        U3 --> U4
    end
    
    subgraph Application["应用场景"]
        A1[实时写入<br/>实时接收数据流]
        A2[批量更新<br/>批量处理数据]
        A3[多数据源<br/>支持多数据源场景]
        A4[故障恢复<br/>故障恢复时判断]
    end
    
    R1 --> C1
    R2 --> U1
    R3 --> A1
    R4 --> A2
    C2 --> A3
    U4 --> A4
    
    style Role fill:#e3f2fd
    style Compare fill:#fff3e0
    style Update fill:#f3e5f5
    style Application fill:#e8f5e9
```

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

Locator 的结构：包含 timestamp、concurrentIdx、hashId 等信息：

```mermaid
flowchart TD
    subgraph Locator["Locator 对象"]
        L[Locator<br/>位置信息]
    end
    
    subgraph Fields["核心字段"]
        F1[SourceId<br/>数据源标识<br/>uint64_t _src]
        F2[MinOffset<br/>最小偏移量<br/>Progress::Offset]
        F3[MultiProgress<br/>多进度信息<br/>每个HashId的进度]
        F4[UserData<br/>用户数据<br/>string _userData]
    end
    
    subgraph DocInfo["DocInfo 文档信息"]
        D1[Timestamp<br/>时间戳<br/>int64_t]
        D2[ConcurrentIdx<br/>并发索引<br/>uint32_t]
        D3[HashId<br/>分片标识<br/>uint16_t]
        D4[SourceIdx<br/>数据源索引<br/>uint8_t]
        D1 --> D2
        D2 --> D3
        D3 --> D4
    end
    
    subgraph Progress["Progress 进度信息"]
        P1[Offset<br/>偏移量]
        P2[Timestamp<br/>时间戳]
        P3[ConcurrentIdx<br/>并发索引]
        P1 --> P2
        P2 --> P3
    end
    
    L --> F1
    L --> F2
    L --> F3
    L --> F4
    F3 -->|包含| P1
    D1 -->|用于| F3
    
    style Locator fill:#e3f2fd
    style Fields fill:#fff3e0
    style DocInfo fill:#f3e5f5
    style Progress fill:#e8f5e9
```

- **timestamp**：时间戳，记录数据的时间位置
- **concurrentIdx**：并发索引，处理时间戳相同的情况
- **hashId**：Hash ID，用于分片
- **sourceIdx**：数据源索引，支持多数据源
- **multiProgress**：多进度信息，每个 hashId 记录自己的进度

### 3.3 Locator 的比较逻辑

Locator 的比较逻辑用于判断数据是否已处理：

Locator 比较：判断数据是否已处理的逻辑（已在上面详细展示，此处不再重复）：

**比较示例**：
- **Locator A**：timestamp=100, hashId=0
- **Locator B**：timestamp=200, hashId=0
- **结果**：B 比 A 快（`LCR_FULLY_FASTER`），说明 B 包含 A 的所有数据

**比较逻辑**：

Locator 的比较逻辑是增量更新的核心算法。让我们通过流程图来理解详细的比较过程：

```mermaid
graph TD
    A[IsFasterThan调用] --> B{数据源是否相同?}
    B -->|否| C[返回LCR_INVALID]
    B -->|是| D[遍历multiProgress]
    D --> E{当前hashId是否存在?}
    E -->|不存在| F{other是否存在?}
    E -->|存在| G[比较Progress]
    F -->|存在| H[返回LCR_PARTIAL_FASTER]
    F -->|不存在| I[继续下一个hashId]
    G --> J{比较结果}
    J -->|LCR_FULLY_FASTER| I
    J -->|其他| K[返回比较结果]
    I --> L{是否遍历完?}
    L -->|否| D
    L -->|是| M[返回LCR_FULLY_FASTER]
    
    style B fill:#e3f2fd
    style G fill:#fff3e0
    style J fill:#f3e5f5
    style M fill:#e8f5e9
```

**比较逻辑详解**：

```cpp
// framework/Locator.h
LocatorCompareResult Locator::IsFasterThan(const Locator& other, 
                                            bool ignoreLegacyDiffSrc) const
{
    // 1. 检查数据源是否相同
    if (!IsSameSrc(other, ignoreLegacyDiffSrc)) {
        return LCR_INVALID;  // 数据源不同，无法比较
    }
    
    // 2. 比较每个 hashId 的进度
    for (size_t i = 0; i < _multiProgress.size(); ++i) {
        if (i >= other._multiProgress.size()) {
            // 当前 Locator 有更多的 hashId，部分更快
            return LCR_PARTIAL_FASTER;
        }
        
        // 比较该 hashId 的进度
        auto result = CompareProgress(_multiProgress[i], other._multiProgress[i]);
        if (result != LCR_FULLY_FASTER) {
            // 如果该 hashId 不是完全更快，返回结果
            return result;
        }
    }
    
    // 3. 所有 hashId 都完全更快，返回完全更快
    return LCR_FULLY_FASTER;
}
```

**比较算法的性能优化**：

1. **快速路径**：
   - 如果数据源不同，直接返回 `LCR_INVALID`，避免遍历 Progress
   - 如果 Progress 数量不同，快速判断部分更快
   
2. **短路优化**：
   - 如果某个 hashId 不是完全更快，立即返回结果
   - 不需要继续比较后续 hashId
   
3. **缓存优化**：
   - 比较结果可以缓存，避免重复计算
   - 对于相同的 Locator 对，直接返回缓存结果
   
4. **位运算优化**：
   - 使用位运算优化 Progress 的比较
   - 减少比较开销，提高比较性能

### 3.4 Locator 的更新

Locator 的更新通过 `Update()` 方法实现：

Locator 更新：更新数据处理位置：

```mermaid
flowchart TD
    subgraph Input["输入"]
        I1[新Locator<br/>New Locator]
        I2[当前Locator<br/>Current Locator]
    end
    
    subgraph Check["检查条件"]
        C1[IsFasterThan<br/>比较新Locator和当前Locator]
        C2{新Locator是否<br/>完全更快?}
        C1 --> C2
    end
    
    subgraph Update["更新操作"]
        U1[更新MultiProgress<br/>更新每个HashId的进度]
        U2[更新MinOffset<br/>更新最小偏移量]
        U3[更新UserData<br/>更新用户数据]
        U4[保证一致性<br/>只向前推进]
        U1 --> U2
        U2 --> U3
        U3 --> U4
    end
    
    subgraph Result["结果"]
        R1[更新成功<br/>Locator已更新]
        R2[更新失败<br/>保持原Locator]
    end
    
    I1 --> C1
    I2 --> C1
    C2 -->|是| U1
    C2 -->|否| R2
    U4 --> R1
    
    style Input fill:#e3f2fd
    style Check fill:#fff3e0
    style Update fill:#f3e5f5
    style Result fill:#e8f5e9
```

**更新逻辑**：
- **条件**：只有当新的 Locator 完全比当前 Locator 快时，才更新
- **更新内容**：更新 `multiProgress`，记录最新的数据处理位置
- **保证一致性**：保证 Locator 只向前推进，不会回退

## 4. 增量更新机制

### 4.1 增量更新的流程

增量更新通过 Locator 判断哪些数据已处理：

增量更新流程：通过 Locator 判断数据是否已处理（已在上面详细展示，此处不再重复）：

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

增量更新判断：通过 Locator 比较判断数据是否已处理：

```mermaid
flowchart TD
    subgraph Input["输入"]
        I1[数据Locator<br/>Data Locator]
        I2[版本Locator<br/>Version Locator]
    end
    
    subgraph Compare["比较判断"]
        C1[IsFasterThan<br/>比较两个Locator]
        C2{比较结果}
    end
    
    subgraph Result["判断结果"]
        R1[LCR_FULLY_FASTER<br/>数据已处理<br/>跳过数据]
        R2[LCR_SLOWER<br/>数据未处理<br/>需要处理]
        R3[LCR_PARTIAL_FASTER<br/>部分数据已处理<br/>需要部分处理]
        R4[LCR_INVALID<br/>数据源不同<br/>无法比较]
    end
    
    subgraph Action["处理动作"]
        A1[跳过数据<br/>不处理]
        A2[处理新数据<br/>构建索引]
        A3[部分处理<br/>处理未处理部分]
        A4[无法判断<br/>需要人工处理]
    end
    
    I1 --> C1
    I2 --> C1
    C1 --> C2
    C2 -->|完全更快| R1
    C2 -->|更慢| R2
    C2 -->|部分更快| R3
    C2 -->|无效| R4
    R1 --> A1
    R2 --> A2
    R3 --> A3
    R4 --> A4
    
    style Input fill:#e3f2fd
    style Compare fill:#fff3e0
    style Result fill:#f3e5f5
    style Action fill:#e8f5e9
```

**判断逻辑**：
- **LCR_FULLY_FASTER**：数据已处理，跳过
- **LCR_SLOWER**：数据未处理，需要处理
- **LCR_PARTIAL_FASTER**：部分数据已处理，需要部分处理
- **LCR_INVALID**：数据源不同，无法比较

### 4.3 增量更新的场景

增量更新适用于以下场景：

增量更新场景：实时写入、批量更新等：

```mermaid
flowchart LR
    subgraph Realtime["实时写入场景"]
        R1[实时接收数据流<br/>Continuous Data Stream]
        R2[检查Locator<br/>IsFasterThan判断]
        R3[处理新数据<br/>只处理未处理数据]
        R4[更新Locator<br/>记录最新进度]
        R5[定期Commit<br/>提交版本]
        R1 --> R2
        R2 --> R3
        R3 --> R4
        R4 --> R5
    end
    
    subgraph Batch["批量更新场景"]
        B1[批量读取数据源<br/>Batch Read]
        B2[检查Locator<br/>过滤已处理数据]
        B3[处理新数据<br/>批量构建索引]
        B4[更新Locator<br/>更新进度]
        B5[批量Commit<br/>提交版本]
        B1 --> B2
        B2 --> B3
        B3 --> B4
        B4 --> B5
    end
    
    subgraph MultiSource["多数据源场景"]
        M1[多个数据源<br/>Multiple Data Sources]
        M2[区分SourceIdx<br/>区分数据源]
        M3[分别处理<br/>独立处理每个数据源]
        M4[保证一致性<br/>数据不重复不丢失]
        M1 --> M2
        M2 --> M3
        M3 --> M4
    end
    
    subgraph Recovery["故障恢复场景"]
        F1[故障恢复<br/>Failure Recovery]
        F2[检查Locator<br/>判断需要重新处理的数据]
        F3[重新处理<br/>处理未处理数据]
        F4[恢复完成<br/>恢复正常状态]
        F1 --> F2
        F2 --> F3
        F3 --> F4
    end
    
    style Realtime fill:#e3f2fd
    style Batch fill:#fff3e0
    style MultiSource fill:#f3e5f5
    style Recovery fill:#e8f5e9
```

**使用场景**：
- **实时写入**：实时接收数据，通过 Locator 判断哪些数据已处理
- **批量更新**：批量处理数据，通过 Locator 避免重复处理
- **多数据源**：从多个数据源读取数据，通过 Locator 保证数据一致性
- **故障恢复**：故障恢复时，通过 Locator 判断需要重新处理的数据

## 5. 版本提交与加载

### 5.1 版本提交流程

版本提交通过 `VersionCommitter` 实现：

版本提交流程：从准备到持久化的完整过程（已在上面详细展示，此处不再重复）：

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

版本加载流程：从磁盘加载版本信息（已在上面详细展示，此处不再重复）：

**加载流程**：
1. **读取版本文件**：从磁盘读取版本文件
2. **解析 Version**：解析 JSON 格式的版本信息
3. **验证 Version**：验证版本的有效性
4. **加载 Segment**：根据 Version 中的 Segment 列表加载 Segment
5. **初始化 TabletData**：初始化 TabletData，设置 Version 和 Segment 列表

### 5.3 版本回滚

版本回滚支持回滚到历史版本：

版本回滚：回滚到历史版本：

```mermaid
flowchart TD
    subgraph Select["选择目标版本"]
        S1[选择目标版本<br/>Select Target Version]
        S2[验证版本存在性<br/>检查版本文件]
        S3[验证版本有效性<br/>检查Segment存在]
        S1 --> S2
        S2 --> S3
    end
    
    subgraph Load["加载目标版本"]
        L1[加载Version<br/>Load Version]
        L2[加载Segment列表<br/>Load Segment List]
        L3[加载Locator<br/>Load Locator]
        L4[加载Schema映射<br/>Load Schema RoadMap]
        L1 --> L2
        L2 --> L3
        L3 --> L4
    end
    
    subgraph Restore["恢复状态"]
        R1[更新TabletData<br/>Update TabletData]
        R2[设置Version<br/>Set Version]
        R3[设置Segment列表<br/>Set Segment List]
        R4[初始化查询器<br/>Initialize Readers]
        R1 --> R2
        R2 --> R3
        R3 --> R4
    end
    
    subgraph Result["回滚结果"]
        RE1[回滚成功<br/>Rollback Success]
        RE2[恢复到目标版本<br/>Restored to Target Version]
        RE3[查询恢复正常<br/>Query Service Restored]
        RE1 --> RE2
        RE2 --> RE3
    end
    
    S3 --> L1
    L4 --> R1
    R4 --> RE1
    
    style Select fill:#e3f2fd
    style Load fill:#fff3e0
    style Restore fill:#f3e5f5
    style Result fill:#e8f5e9
```

**回滚流程**：
1. **选择目标版本**：选择要回滚到的目标版本
2. **验证版本**：验证目标版本的有效性
3. **加载版本**：加载目标版本的 Version 和 Segment
4. **更新 TabletData**：更新 TabletData，恢复到目标版本

## 6. Schema 演进

### 6.1 Schema 演进机制

IndexLib 支持 Schema 演进，每个 Segment 可以有不同的 Schema：

Schema 演进：支持 Schema 变更，每个 Segment 记录自己的 SchemaId：

```mermaid
flowchart LR
    subgraph Schema["Schema 演进机制"]
        S1[Segment SchemaId<br/>每个Segment记录自己的SchemaId]
        S2[Schema版本映射<br/>SchemaVersionRoadMap]
        S3[兼容性检查<br/>Schema兼容性验证]
        S1 --> S2
        S2 --> S3
    end
    
    subgraph Version["版本演进"]
        V1[Version 1<br/>SchemaId: 0]
        V2[Version 2<br/>SchemaId: 0]
        V3[Version 3<br/>SchemaId: 1]
        V1 -->|Schema变更| V2
        V2 -->|新Segment使用新Schema| V3
    end
    
    subgraph Segment["Segment Schema"]
        SE1[Segment 1<br/>SchemaId: 0]
        SE2[Segment 2<br/>SchemaId: 0]
        SE3[Segment 3<br/>SchemaId: 1]
        SE4[Segment 4<br/>SchemaId: 1]
    end
    
    subgraph Compatibility["兼容性保证"]
        C1[向后兼容<br/>新Schema向后兼容旧Schema]
        C2[渐进式迁移<br/>新Segment使用新Schema]
        C3[旧Segment保持<br/>旧Segment保持原样]
        C1 --> C2
        C2 --> C3
    end
    
    V1 --> SE1
    V2 --> SE2
    V3 --> SE3
    V3 --> SE4
    S3 --> C1
    
    style Schema fill:#e3f2fd
    style Version fill:#fff3e0
    style Segment fill:#f3e5f5
    style Compatibility fill:#e8f5e9
```

**Schema 演进机制**：
- **Segment SchemaId**：每个 Segment 记录自己的 `SchemaId`
- **Schema 版本映射**：Version 维护 `SchemaVersionRoadMap`，记录 Schema 版本映射
- **兼容性检查**：Schema 变更时检查兼容性，保证数据一致性

### 6.2 Schema 变更流程

Schema 变更的流程：

Schema 变更流程：从 Schema 变更到版本提交：

```mermaid
flowchart TD
    subgraph Check["检查兼容性"]
        C1[检查新Schema<br/>Check New Schema]
        C2[检查兼容性<br/>Check Compatibility]
        C3{兼容性检查<br/>通过?}
        C1 --> C2
        C2 --> C3
    end
    
    subgraph Seal["Seal 当前Segment"]
        S1[Seal当前Segment<br/>Seal Current Segment]
        S2[停止接收新文档<br/>Stop Receiving Documents]
        S3[等待转储完成<br/>Wait for Dump]
        S1 --> S2
        S2 --> S3
    end
    
    subgraph Create["创建新Segment"]
        CR1[使用新Schema<br/>Use New Schema]
        CR2[创建新MemSegment<br/>Create New MemSegment]
        CR3[开始接收新文档<br/>Start Receiving Documents]
        CR1 --> CR2
        CR2 --> CR3
    end
    
    subgraph Commit["提交版本"]
        CO1[更新SchemaId<br/>Update SchemaId]
        CO2[更新SchemaVersionRoadMap<br/>Update RoadMap]
        CO3[提交Version<br/>Commit Version]
        CO1 --> CO2
        CO2 --> CO3
    end
    
    C3 -->|通过| S1
    C3 -->|失败| Error[Schema变更失败]
    S3 --> CR1
    CR3 --> CO1
    CO3 --> Success[Schema变更成功]
    
    style Check fill:#e3f2fd
    style Seal fill:#fff3e0
    style Create fill:#f3e5f5
    style Commit fill:#e8f5e9
```

**变更流程**：
1. **检查兼容性**：检查新 Schema 与旧 Schema 的兼容性
2. **Seal 当前 Segment**：Seal 当前构建中的 Segment
3. **创建新 Segment**：使用新 Schema 创建新的 Segment
4. **提交版本**：Commit 时更新 SchemaId 和 SchemaVersionRoadMap

## 7. 版本清理

### 7.1 版本清理机制

版本清理用于清理不再需要的旧版本文件：

版本清理：清理不再需要的旧版本文件：

```mermaid
flowchart TD
    subgraph Identify["识别清理目标"]
        I1[保留版本列表<br/>Keep Recent N Versions]
        I2[识别旧版本<br/>Identify Old Versions]
        I3[检查版本引用<br/>Check Version References]
        I1 --> I2
        I2 --> I3
    end
    
    subgraph CleanSegment["清理Segment"]
        CS1[检查Segment引用<br/>Check Segment References]
        CS2{Segment是否<br/>被引用?}
        CS3[清理Segment文件<br/>Delete Segment Files]
        CS4[清理索引文件<br/>Delete Index Files]
        CS1 --> CS2
        CS2 -->|否| CS3
        CS3 --> CS4
    end
    
    subgraph CleanVersion["清理版本文件"]
        CV1[清理版本文件<br/>Delete Version Files]
        CV2[清理Fence目录<br/>Delete Fence Directories]
        CV3[清理元数据<br/>Delete Metadata]
        CV1 --> CV2
        CV2 --> CV3
    end
    
    subgraph Result["清理结果"]
        R1[释放存储空间<br/>Free Storage Space]
        R2[保持系统稳定<br/>Maintain System Stability]
        R1 --> R2
    end
    
    I3 --> CS1
    CS2 -->|是| Skip[跳过清理]
    CS4 --> CV1
    CV3 --> R1
    
    style Identify fill:#e3f2fd
    style CleanSegment fill:#fff3e0
    style CleanVersion fill:#f3e5f5
    style Result fill:#e8f5e9
```

**清理机制**：
- **保留版本列表**：保留指定数量的版本，清理其他版本
- **清理 Segment**：清理不再被任何版本引用的 Segment
- **清理索引文件**：清理不再使用的索引文件

### 7.2 版本清理策略

版本清理的策略：

版本清理策略：保留版本数量、清理时机等：

```mermaid
flowchart LR
    subgraph Strategy["清理策略"]
        S1[保留版本数<br/>Keep N Versions]
        S2[清理时机<br/>Cleanup Timing]
        S3[清理范围<br/>Cleanup Scope]
        S1 --> S2
        S2 --> S3
    end
    
    subgraph Keep["保留策略"]
        K1[保留最近N个版本<br/>Keep Recent N Versions]
        K2[保留活跃版本<br/>Keep Active Versions]
        K3[保留重要版本<br/>Keep Important Versions]
    end
    
    subgraph Timing["清理时机"]
        T1[Commit时清理<br/>Cleanup on Commit]
        T2[定期清理<br/>Periodic Cleanup]
        T3[手动清理<br/>Manual Cleanup]
    end
    
    subgraph Scope["清理范围"]
        SC1[版本文件<br/>Version Files]
        SC2[Segment文件<br/>Segment Files]
        SC3[索引文件<br/>Index Files]
        SC4[元数据文件<br/>Metadata Files]
    end
    
    S1 --> K1
    S2 --> T1
    S3 --> SC1
    K1 --> T1
    T1 --> SC1
    SC1 --> SC2
    SC2 --> SC3
    SC3 --> SC4
    
    style Strategy fill:#e3f2fd
    style Keep fill:#fff3e0
    style Timing fill:#f3e5f5
    style Scope fill:#e8f5e9
```

**清理策略**：
- **保留版本数**：保留最近 N 个版本，清理其他版本
- **清理时机**：在 Commit 时或定期清理
- **清理范围**：清理版本文件、Segment 文件、索引文件等

## 8. 增量更新的实际应用

### 8.1 实时写入场景

在实时写入场景中，增量更新的应用：

实时写入场景中的增量更新：通过 Locator 判断数据是否已处理：

```mermaid
flowchart TD
    subgraph Receive["接收数据"]
        R1[实时接收数据流<br/>Receive Data Stream]
        R2[解析文档<br/>Parse Documents]
        R3[提取Locator<br/>Extract Locator]
        R1 --> R2
        R2 --> R3
    end
    
    subgraph Check["检查Locator"]
        C1[获取Version Locator<br/>Get Version Locator]
        C2[IsFasterThan比较<br/>Compare Locators]
        C3{数据是否<br/>已处理?}
        C1 --> C2
        C2 --> C3
    end
    
    subgraph Process["处理新数据"]
        P1[处理新数据<br/>Process New Data]
        P2[构建索引<br/>Build Index]
        P3[更新Locator<br/>Update Locator]
        P1 --> P2
        P2 --> P3
    end
    
    subgraph Commit["提交版本"]
        CO1[定期Commit<br/>Periodic Commit]
        CO2[更新Version Locator<br/>Update Version Locator]
        CO3[持久化版本<br/>Persist Version]
        CO1 --> CO2
        CO2 --> CO3
    end
    
    R3 --> C1
    C3 -->|未处理| P1
    C3 -->|已处理| Skip[跳过数据]
    P3 --> CO1
    
    style Receive fill:#e3f2fd
    style Check fill:#fff3e0
    style Process fill:#f3e5f5
    style Commit fill:#e8f5e9
```

**实时写入流程**：
1. **接收数据**：实时接收数据流
2. **检查 Locator**：通过 `IsFasterThan()` 判断数据是否已处理
3. **处理新数据**：只处理未处理的数据
4. **更新 Locator**：处理完成后更新 Locator
5. **提交版本**：定期 Commit，更新 Version 的 Locator

### 8.2 批量更新场景

在批量更新场景中，增量更新的应用：

批量更新场景中的增量更新：批量处理数据，避免重复处理：

```mermaid
flowchart TD
    subgraph Read["读取数据源"]
        RD1[批量读取数据<br/>Batch Read Data]
        RD2[解析文档<br/>Parse Documents]
        RD3[提取Locator<br/>Extract Locators]
        RD1 --> RD2
        RD2 --> RD3
    end
    
    subgraph Filter["过滤已处理数据"]
        F1[获取Version Locator<br/>Get Version Locator]
        F2[批量比较Locator<br/>Batch Compare Locators]
        F3[过滤已处理数据<br/>Filter Processed Data]
        F1 --> F2
        F2 --> F3
    end
    
    subgraph Process["处理新数据"]
        P1[批量处理新数据<br/>Batch Process New Data]
        P2[批量构建索引<br/>Batch Build Index]
        P3[更新Locator<br/>Update Locator]
        P1 --> P2
        P2 --> P3
    end
    
    subgraph Commit["提交版本"]
        CO1[批量Commit<br/>Batch Commit]
        CO2[更新Version Locator<br/>Update Version Locator]
        CO3[持久化版本<br/>Persist Version]
        CO1 --> CO2
        CO2 --> CO3
    end
    
    RD3 --> F1
    F3 --> P1
    P3 --> CO1
    
    style Read fill:#e3f2fd
    style Filter fill:#fff3e0
    style Process fill:#f3e5f5
    style Commit fill:#e8f5e9
```

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

版本管理的原子性：通过 Fence 机制保证版本提交的原子性：

```mermaid
flowchart LR
    subgraph Fence["Fence 机制"]
        F1[创建Fence目录<br/>Create Fence Directory]
        F2[写入版本文件<br/>Write Version File]
        F3[原子重命名<br/>Atomic Rename]
        F1 --> F2
        F2 --> F3
    end
    
    subgraph Atomicity["原子性保证"]
        A1[要么全部成功<br/>All or Nothing]
        A2[要么全部失败<br/>Rollback on Failure]
        A3[避免部分写入<br/>Avoid Partial Write]
        A1 --> A2
        A2 --> A3
    end
    
    subgraph Error["错误处理"]
        E1[提交失败<br/>Commit Failure]
        E2[清理Fence目录<br/>Cleanup Fence]
        E3[不影响已有版本<br/>No Impact on Existing]
        E1 --> E2
        E2 --> E3
    end
    
    subgraph Advantage["设计优势"]
        AD1[原子性<br/>Atomicity]
        AD2[性能高<br/>High Performance]
        AD3[可靠性<br/>Reliability]
        AD4[简单性<br/>Simplicity]
    end
    
    F3 --> A1
    A3 --> E1
    E3 --> AD1
    
    style Fence fill:#e3f2fd
    style Atomicity fill:#fff3e0
    style Error fill:#f3e5f5
    style Advantage fill:#e8f5e9
```

**原子性保证**：
- **Fence 机制**：通过 Fence 目录保证版本提交的原子性
- **原子切换**：原子性地将 Fence 目录切换为正式版本目录
- **错误恢复**：如果提交失败，可以清理 Fence 目录，不影响已有版本

### 9.2 数据一致性

版本管理保证数据一致性：

版本管理的数据一致性：通过 Locator 保证数据不重复、不丢失：

```mermaid
flowchart TD
    subgraph Consistency["数据一致性保证"]
        C1[不重复保证<br/>No Duplication]
        C2[不丢失保证<br/>No Loss]
        C3[多数据源支持<br/>Multi-Source Support]
    end
    
    subgraph Locator["Locator 机制"]
        L1[Locator比较<br/>Locator Comparison]
        L2[IsFasterThan<br/>判断数据是否已处理]
        L3[Update机制<br/>保证只向前推进]
        L1 --> L2
        L2 --> L3
    end
    
    subgraph MultiSource["多数据源支持"]
        M1[SourceIdx区分<br/>Distinguish by SourceIdx]
        M2[独立处理<br/>Independent Processing]
        M3[保证一致性<br/>Ensure Consistency]
        M1 --> M2
        M2 --> M3
    end
    
    subgraph Concurrent["并发控制"]
        CO1[ConcurrentIdx<br/>处理时间戳相同]
        CO2[HashId分片<br/>Sharding by HashId]
        CO3[保证顺序<br/>Ensure Order]
        CO1 --> CO2
        CO2 --> CO3
    end
    
    C1 --> L1
    C2 --> L3
    C3 --> M1
    L3 --> CO1
    
    style Consistency fill:#e3f2fd
    style Locator fill:#fff3e0
    style MultiSource fill:#f3e5f5
    style Concurrent fill:#e8f5e9
```

**数据一致性保证**：
- **Locator 比较**：通过 Locator 比较判断数据是否已处理
- **多数据源支持**：支持多数据源场景，通过 `sourceIdx` 区分数据源
- **并发控制**：通过 `concurrentIdx` 处理时间戳相同的情况

### 9.3 性能优化

版本管理的性能优化：

版本管理的性能优化：版本缓存、懒加载等：

```mermaid
flowchart LR
    subgraph Cache["版本缓存"]
        CA1[缓存常用版本<br/>Cache Common Versions]
        CA2[LRU淘汰策略<br/>LRU Eviction]
        CA3[减少磁盘读取<br/>Reduce Disk Reads]
        CA1 --> CA2
        CA2 --> CA3
    end
    
    subgraph Lazy["懒加载"]
        L1[按需加载版本<br/>Load on Demand]
        L2[减少启动时间<br/>Reduce Startup Time]
        L3[并行加载<br/>Parallel Loading]
        L1 --> L2
        L2 --> L3
    end
    
    subgraph Batch["批量操作"]
        B1[批量处理版本<br/>Batch Process Versions]
        B2[批量清理<br/>Batch Cleanup]
        B3[提高效率<br/>Improve Efficiency]
        B1 --> B2
        B2 --> B3
    end
    
    subgraph Optimize["优化策略"]
        O1[快速路径<br/>Fast Path]
        O2[短路优化<br/>Short Circuit]
        O3[缓存优化<br/>Cache Optimization]
        O1 --> O2
        O2 --> O3
    end
    
    CA3 --> L1
    L3 --> B1
    B3 --> O1
    
    style Cache fill:#e3f2fd
    style Lazy fill:#fff3e0
    style Batch fill:#f3e5f5
    style Optimize fill:#e8f5e9
```

**性能优化策略**：
- **版本缓存**：缓存常用版本，减少磁盘读取
- **懒加载**：按需加载版本信息，减少启动时间
- **批量操作**：批量处理版本操作，提高效率

## 10. 性能优化与最佳实践

### 10.1 版本管理性能优化

**优化策略**：

1. **版本缓存优化**：
   - **缓存策略**：缓存常用版本，减少磁盘读取
   - **缓存大小**：根据内存情况调整缓存大小
   - **缓存淘汰**：使用 LRU 等策略淘汰不常用的版本
   
2. **版本加载优化**：
   - **懒加载**：按需加载版本信息，减少启动时间
   - **并行加载**：多个版本可以并行加载，提高加载速度
   - **预加载**：预加载常用版本，减少查询延迟
   
3. **版本清理优化**：
   - **延迟清理**：延迟清理旧版本，避免影响查询
   - **批量清理**：批量清理旧版本，减少 IO 开销
   - **清理策略**：根据版本使用情况选择清理策略

### 10.2 Locator 性能优化

**优化策略**：

1. **比较优化**：
   - **快速路径**：数据源不同时直接返回，避免遍历
   - **短路优化**：部分 hashId 不满足时立即返回
   - **缓存优化**：缓存比较结果，避免重复计算
   
2. **序列化优化**：
   - **压缩序列化**：使用压缩算法减少序列化大小
   - **增量序列化**：只序列化变更部分，减少序列化开销
   - **批量序列化**：批量序列化多个 Locator，提高效率
   
3. **更新优化**：
   - **批量更新**：批量更新多个 hashId 的进度
   - **增量更新**：只更新变更的进度，减少更新开销
   - **异步更新**：异步更新 Locator，不阻塞主流程

### 10.3 增量更新性能优化

**优化策略**：

1. **数据过滤优化**：
   - **批量过滤**：批量过滤已处理数据，减少比较次数
   - **索引优化**：使用索引加速数据过滤
   - **并行过滤**：多个数据源可以并行过滤
   
2. **处理优化**：
   - **批量处理**：批量处理新数据，提高处理效率
   - **并行处理**：多个 hashId 可以并行处理
   - **流式处理**：边读取边处理，减少内存占用
   
3. **Locator 更新优化**：
   - **延迟更新**：延迟更新 Locator，减少更新频率
   - **批量更新**：批量更新多个 hashId 的进度
   - **异步更新**：异步更新 Locator，不阻塞数据处理

## 11. 小结

版本管理和增量更新是 IndexLib 的核心功能，通过 Version 和 Locator 两个机制实现。通过本文的深入解析，我们了解到：

**核心机制**：

- **Version**：版本信息，记录索引包含哪些 Segment，支持版本演进和 Schema 演进
  - **版本控制**：版本号单调递增，支持版本回滚
  - **Schema 演进**：每个 Segment 记录自己的 SchemaId，支持 Schema 变更
  - **持久化**：通过 Fence 机制保证版本提交的原子性
  
- **Locator**：位置信息，记录数据处理位置，用于增量更新和数据一致性保证
  - **多维度定位**：通过 timestamp、concurrentIdx、hashId、sourceIdx 等多维度定位
  - **比较算法**：通过 `IsFasterThan()` 判断数据是否已处理
  - **更新机制**：保证 Locator 只向前推进，不会回退
  
- **版本演进**：每次 Commit 都会创建新版本，版本号递增，支持版本回滚
  - **版本号递增**：版本号严格单调递增，保证版本顺序
  - **版本历史**：保留版本历史，支持查看和回滚
  - **版本清理**：定期清理旧版本，释放存储空间
  
- **增量更新**：通过 Locator 判断哪些数据已处理，避免重复处理，支持实时写入和批量更新
  - **数据过滤**：通过 Locator 比较过滤已处理数据
  - **进度追踪**：记录每个 HashId 的处理进度，支持分片处理
  - **多数据源支持**：支持多数据源场景，保证数据一致性
  
- **Schema 演进**：支持 Schema 变更，每个 Segment 记录自己的 SchemaId
  - **向后兼容**：新 Schema 向后兼容旧 Schema
  - **渐进式迁移**：新 Segment 使用新 Schema，旧 Segment 保持原样
  - **版本映射**：通过 SchemaVersionRoadMap 记录 Schema 版本映射
  
- **原子性保证**：通过 Fence 机制保证版本提交的原子性
  - **Fence 目录**：创建临时目录，写入版本文件
  - **原子切换**：原子性地将 Fence 目录切换为正式版本目录
  - **错误恢复**：提交失败时清理 Fence 目录，不影响已有版本
  
- **数据一致性**：通过 Locator 保证数据不重复、不丢失，支持多数据源场景
  - **不重复保证**：通过 Locator 比较保证数据不重复处理
  - **不丢失保证**：通过 Locator 更新保证数据不丢失
  - **多数据源支持**：通过 `sourceIdx` 区分数据源，支持多数据源场景

**设计亮点**：

1. **Fence 机制**：通过原子重命名保证版本提交的原子性，实现简单、性能高
2. **Locator 比较算法**：多维度比较算法，支持精确的数据定位和增量更新
3. **Schema 演进**：支持 Schema 变更，每个 Segment 记录自己的 SchemaId，实现渐进式迁移
4. **版本清理**：定期清理旧版本，释放存储空间，保证系统稳定性
5. **性能优化**：通过缓存、懒加载、批量操作等机制优化性能

**性能优化**：

- **版本提交**：Fence 机制保证原子性，提交延迟较低
- **Locator 比较**：快速路径和短路优化，显著提升比较性能
- **增量更新**：通过 Locator 过滤，有效减少处理量
- **版本加载**：懒加载和并行加载，有效减少启动时间

理解版本管理和增量更新，是掌握 IndexLib 数据管理机制的关键。在下一篇文章中，我们将深入介绍 Segment 合并策略的实现细节，包括合并策略的选择、合并计划的创建、合并执行的流程等各个组件的实现原理和性能优化策略。
