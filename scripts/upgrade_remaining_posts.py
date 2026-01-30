#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch-upgrade remaining placeholder/template posts.

Goal:
- Replace the generic "这篇笔记围绕..." template body with topic-specific, readable engineering notes.
- Replace diagram references from /images/diagrams/generated/... to stable, reusable SVGs under images/diagrams/.

This script is intentionally conservative:
- Keeps YAML front matter unchanged.
- Only rewrites posts that still contain the template marker phrase.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "_posts"
DIAGRAMS_DIR = ROOT / "images" / "diagrams"

TEMPLATE_MARKER = "这篇笔记围绕"


def split_front_matter(text: str) -> Tuple[str, str]:
    """
    Return (front_matter, body). front_matter includes the surrounding --- lines.
    """
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    # parts: ["", "\n<yaml>\n", "\n<body>..."]
    fm = "---" + parts[1] + "---"
    body = parts[2].lstrip("\n")
    return fm.strip() + "\n", body


def extract_title(front_matter: str) -> str:
    m = re.search(r"^title:\s*\"([^\"]+)\"|^title:\s*'([^']+)'|^title:\s*(.+)$", front_matter, re.M)
    if not m:
        return ""
    return (m.group(1) or m.group(2) or m.group(3) or "").strip()


def topic_from_filename(path: Path) -> str:
    m = re.search(r"note-\d+-([a-z0-9-]+)\.md$", path.name)
    return m.group(1) if m else "unknown"


@dataclass(frozen=True)
class UpgradePlan:
    diagram: str  # relative to /images/diagrams/
    body: str


def plan_for_post(topic: str, title: str) -> UpgradePlan:
    """
    Map topic -> (diagram, body template).
    For topic == "post", infer subtopic from title keywords.
    """
    # Reuse diagrams we already have (stable names).
    if topic == "cfs":
        return UpgradePlan(
            diagram="linux-cfs-vruntime-runqueue.svg",
            body=_body_cfs(title),
        )
    if topic == "http-2":
        return UpgradePlan(
            diagram="http2-multiplexing-flow-control.svg",
            body=_body_http2(title),
        )
    if topic == "simd":
        return UpgradePlan(
            diagram="simd-speedup-limits.svg",
            body=_body_simd(title),
        )
    if topic == "nvme":
        return UpgradePlan(
            diagram="nvme-queue-submission-completion.svg",
            body=_body_nvme(title),
        )
    if topic == "ssd-ftl":
        return UpgradePlan(
            diagram="ssd-ftl-mapping-gc-wa.svg",
            body=_body_ssd_ftl(title),
        )
    if topic == "tombstone":
        return UpgradePlan(
            diagram="tombstone-compaction-lifecycle.svg",
            body=_body_tombstone(title),
        )
    if topic == "bloom-ribbon-filter":
        return UpgradePlan(
            diagram="bloom-filter-sizing.svg",
            body=_body_bloom(title),
        )
    if topic == "profile-ipc-cache-miss-branch-miss":
        return UpgradePlan(
            diagram="profile-metrics-ipc-cache-branch.svg",
            body=_body_profile_metrics(title),
        )
    if topic == "vs":
        return UpgradePlan(
            diagram="l4-vs-l7-load-balancing.svg",
            body=_body_l4_l7(title),
        )
    if topic == "read-after-write-list":
        return UpgradePlan(
            diagram="object-storage-consistency-put-get-list.svg",
            body=_body_object_consistency(title),
        )
    if topic == "write-stall":
        return UpgradePlan(
            diagram="rocksdb-flush-l0-stall.svg",
            body=_body_rocksdb_write_stall(title),
        )
    if topic == "memtable-immutable":
        return UpgradePlan(
            diagram="rocksdb-write-path.svg",
            body=_body_rocksdb_memtable_immutable(title),
        )
    if topic == "tcp-rto-fast-retransmit":
        return UpgradePlan(
            diagram="tcp-retransmit-rto-fast.svg",
            body=_body_tcp_rto_fast(title),
        )
    if topic == "tls":
        return UpgradePlan(
            diagram="tls-handshake-keys.svg",
            body=_body_tls(title),
        )
    if topic == "cubic-bbr":
        return UpgradePlan(
            diagram="tcp-cc-cubic-bbr.svg",
            body=_body_cubic_bbr(title),
        )
    if topic == "cache-line":
        return UpgradePlan(
            diagram="cache-line-false-sharing.svg",
            body=_body_cache_line(title),
        )
    if topic == "flush":
        return UpgradePlan(
            diagram="branch-miss-pipeline-flush.svg",
            body=_body_pipeline_flush(title),
        )
    if topic == "fence":
        return UpgradePlan(
            diagram="memory-reorder-fence.svg",
            body=_body_fence(title),
        )
    if topic == "io-uring-io":
        return UpgradePlan(
            diagram="io-uring-sq-cq.svg",
            body=_body_io_uring(title),
        )
    if topic == "merge":
        return UpgradePlan(
            diagram="storage-write-merge-log-to-segment.svg",
            body=_body_storage_merge(title),
        )
    if topic == "cpu-io":
        return UpgradePlan(
            diagram="cpu-vs-io-bound.svg",
            body=_body_cpu_io(title),
        )
    if topic == "ec":
        return UpgradePlan(
            diagram="erasure-coding-layout.svg",
            body=_body_ec(title),
        )
    if topic == "bucket-key-prefix":
        return UpgradePlan(
            diagram="object-storage-bucket-prefix-partition.svg",
            body=_body_bucket_prefix(title),
        )
    if topic == "rpo-rto":
        return UpgradePlan(
            diagram="rpo-rto-tradeoff.svg",
            body=_body_rpo_rto(title),
        )
    if topic == "quorum":
        return UpgradePlan(
            diagram="quorum-majority.svg",
            body=_body_quorum(title),
        )
    if topic == "leader-lease":
        return UpgradePlan(
            diagram="leader-lease-timeline.svg",
            body=_body_leader_lease(title),
        )
    if topic == "matchindex":
        return UpgradePlan(
            diagram="raft-matchindex-commit.svg",
            body=_body_matchindex(title),
        )
    if topic == "joint-consensus":
        return UpgradePlan(
            diagram="raft-joint-consensus.svg",
            body=_body_joint_consensus(title),
        )

    # "post" means "misc topic", infer by Chinese keywords in title
    if topic == "post":
        if "脑裂" in title:
            return UpgradePlan("consensus-split-brain.svg", _body_split_brain(title))
        if "线性一致性" in title:
            return UpgradePlan("consensus-linearizability-client.svg", _body_linearizability(title))
        if "超时" in title or "重试" in title:
            return UpgradePlan("network-timeout-retry-amplification.svg", _body_timeout_retry(title))
        if "元数据" in title or "对象索引" in title or "目录" in title:
            return UpgradePlan("object-storage-metadata-index.svg", _body_object_metadata(title))
        # default misc
        return UpgradePlan("note-generic-model-metrics.svg", _body_generic_post(title))

    # Unknown: still replace template with a generic engineering-note structure.
    return UpgradePlan("note-generic-model-metrics.svg", _body_generic_post(title))


def build_body(title: str, diagram: str, body: str) -> str:
    header = []
    if title:
        header.append(f"本文围绕「{title}」做一次**工程化**的梳理：先定义语义/模型，再给出可观测信号与排障顺序。")
    else:
        header.append("本文做一次工程化梳理：先定义语义/模型，再给出可观测信号与排障顺序。")
    header.append("")
    header.append(f"![{title or '示意图'}](/images/diagrams/{diagram})")
    header.append("")
    return "\n".join(header) + body.strip() + "\n"


def ensure_diagrams(diagrams_needed: Dict[str, str]) -> None:
    """
    Create missing diagram files with simple, reusable SVGs.
    diagrams_needed: filename -> title text (for SVG header)
    """
    DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, title in diagrams_needed.items():
        path = DIAGRAMS_DIR / filename
        if path.exists():
            continue
        svg = _simple_box_svg(title)
        path.write_text(svg, encoding="utf-8")


def _simple_box_svg(title: str) -> str:
    title = title.replace("&", "and")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 280">
  <defs>
    <style>
      .box{{fill:#fff;stroke:#333;stroke-width:2;rx:14}}
      .title{{font:700 18px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial;fill:#111}}
      .muted{{font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial;fill:#666}}
      .t{{font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial;fill:#222}}
    </style>
  </defs>
  <text class="title" x="40" y="46">{title}</text>
  <text class="muted" x="40" y="72">（占位图已替换为固定命名 SVG，后续可继续迭代为更详细的图）</text>
  <rect class="box" x="40" y="95" width="900" height="150"/>
  <text class="t" x="70" y="140">- 语义/模型：把问题说清楚</text>
  <text class="t" x="70" y="170">- 观测信号：哪些指标能验证你的推断</text>
  <text class="t" x="70" y="200">- 排障顺序：先定位瓶颈，再做调整</text>
</svg>
"""


# ----------------------------- body templates -----------------------------

def _body_cfs(title: str) -> str:
    return """
## 1. 核心直觉：公平不是“每人一样”，而是“按权重欠账”

- **vruntime**：越小越“欠账”，越优先运行。
- **nice/权重**：权重高 → vruntime 增长慢 → 更容易被选中。
- **slice**：runnable 越多，单个任务分到的时间片越短，但也会有最小粒度防止过度切换。

## 2. 线上最常见的症状

- 平均 CPU 不高，但 **P99 抖动**：关键线程没拿到 CPU（热点核/绑核/干扰）。
- 切换过多：线程数过多或时间片太碎，切换开销吞掉吞吐。

## 3. 观测与排障顺序

1. 看 **per-core** 的 runqueue/利用率（不要只看平均）。
2. 看关键线程 on-CPU/off-CPU（慢时到底在跑还是在等）。
3. 看 context switch 与干扰源（后台任务、中断、邻居噪声）。
"""


def _body_http2(title: str) -> str:
    return """
## 1. 最小模型：connection / stream / frame

- 一个 TCP 连接上跑多个 **stream**（请求-响应通道）。
- 数据以 **frame** 交错发送（多路复用）。

## 2. 关键点：HTTP/2 仍可能被 TCP 层 HoL 拖住

丢包导致 TCP 必须按序交付字节流 → 同连接内多个 stream 可能一起变慢。

## 3. 排障顺序

1. 先看丢包/重传（这是最常见根因）。
2. 再看流控/背压（慢消费者拖慢连接）。
3. 最后看 CPU（TLS/HPACK/协议栈）。
"""


def _body_simd(title: str) -> str:
    return """
## 1. 什么时候 SIMD 最容易有效

- 计算密集、分支少、访问规整。

## 2. 三个常见上限

- memory-bound：带宽/缓存 miss 主导。
- control-bound：分支与数据依赖。
- 数据布局/对齐：AoS/SoA、跨 cache line、gather 成本。

## 3. 验证方法

先确认编译器是否真的向量化；再看 IPC/cache miss/branch miss 是否变好。
"""


def _body_nvme(title: str) -> str:
    return """
## 1. NVMe 的核心直觉：多队列并行 + 低协议开销

- 每核/每线程可绑定独立 SQ/CQ，减少锁竞争。
- 设备侧也有更强并行能力。

## 2. 为什么线上“还是会抖”

- 队列深度过高导致排队等待放大 P99。
- 后台任务抢 IO/CPU（flush/compaction/GC/rebuild）。

## 3. 排障顺序

1. 看延迟分位数与队列（in-flight/QD）。
2. 看后台欠账与抢占。
3. 最后看 CPU/锁/软件栈开销。
"""


def _body_ssd_ftl(title: str) -> str:
    return """
## 1. FTL 解决的是什么

Flash 不能原地覆盖写 → 需要 LBA→PPA 映射与 GC 回收。

## 2. 写放大：主机侧 vs 设备侧

- Host WA：WAL/compaction/rewrite 等。
- Device WA：FTL 搬运/擦除带来的额外写入。

## 3. 排障顺序

1. 看是否接近满盘（GC 非线性变贵）。
2. 看随机 overwrite 占比。
3. 区分 host/device WA（别全怪上层）。
"""


def _body_tombstone(title: str) -> str:
    return """
## 1. 删除不等于释放

删除写入 tombstone；空间回收发生在 compaction/合并淘汰旧版本之后。

## 2. 常见现象

- “删了还涨盘”：tombstone 堆积 + compaction 跟不上。

## 3. 排障顺序

1. 看 compaction backlog。
2. 看 tombstone 比例与覆盖写模式。
3. 看是否存在长时间保留旧版本的条件（snapshot/TTL/版本化策略）。
"""


def _body_bloom(title: str) -> str:
    return """
## 1. Bloom 的工程语义：省掉“白跑一趟”

Bloom 主要减少 negative lookup 的无效 IO。

## 2. 两个参数与一个代价

- bits-per-key → 影响假阳性。
- 假阳性 → 额外 IO/CPU（但通常仍比读盘便宜）。

## 3. 排障顺序

先看 negative lookup 占比与过滤命中；再看 cache；最后看 compaction 是否导致 filter 无效或 miss。
"""


def _body_profile_metrics(title: str) -> str:
    return """
## 1. 三个指标的直觉

- IPC：每周期完成多少指令（高不一定快，但低通常有问题）。
- cache miss：访存是否拖住流水线。
- branch miss：分支预测失败导致 flush。

## 2. 排障顺序

1. 先定位瓶颈：CPU 还是 IO/锁。
2. 再看 IPC/cycles 的变化。
3. 最后看 cache/branch 的根因（数据布局、分支形态、热点函数）。
"""


def _body_l4_l7(title: str) -> str:
    return """
## 1. L4 vs L7 的差别

- L4 看五元组/连接：快、稳、简单。
- L7 看应用协议：可路由/鉴权/限流，但成本更高。

## 2. 选型建议

延迟敏感/高吞吐：优先 L4；需要内容路由/安全策略：再引入 L7。
"""


def _body_object_consistency(title: str) -> str:
    return """
## 1. 先区分 GET 与 LIST

GET 更容易强一致；LIST 常依赖目录索引异步更新，天然更容易滞后。

## 2. 常用补语义方法

- commit marker/manifest
- versioning + 条件读（etag/versionId）
- 元数据强一致（DB/KV）+ 对象存 payload
"""


def _body_rocksdb_write_stall(title: str) -> str:
    return """
## 1. write stall 的本质：欠账保护

常见触发链路：immutable 堆积 / L0 堆积 / compaction 欠账 → throttle/stall。

## 2. 排障顺序

1. 看 immutable/L0/backlog 是否持续上升。
2. 看 flush vs compaction 谁更慢（IO 还是 CPU）。
3. 再谈参数与预算（先归因后调参）。
"""


def _body_rocksdb_memtable_immutable(title: str) -> str:
    return """
## 1. 写入高峰时发生了什么

mutable memtable 写满 → 变 immutable → 后台 flush 生成 SST（通常到 L0）。

## 2. 典型告警信号

- immutable 数量持续上升
- L0 文件数上升
- stall/throttle 次数增加

## 3. 排障顺序

先确认 flush 是否跟得上，再看 compaction 是否欠账，最后再调预算/并行度。
"""


def _body_tcp_rto_fast(title: str) -> str:
    return """
## 1. RTO vs fast retransmit

- **fast retransmit**：基于重复 ACK 的快速重传（更快）。
- **RTO**：基于超时的重传（更慢，且会影响尾延迟）。

## 2. 线上现象

丢包→重传→RTT 抖动→应用超时/重试→放大流量与抖动。

## 3. 排障顺序

先看丢包/重传，再看拥塞/队列（bufferbloat），最后看应用层超时与重试策略。
"""


def _body_tls(title: str) -> str:
    return """
## 1. TLS 给你什么

机密性、完整性、身份认证（通常通过证书）。

## 2. 性能关注点

- 握手 RTT（尤其是跨地域）
- 密钥交换与证书校验 CPU
- 连接复用/会话恢复对延迟的影响

## 3. 排障顺序

先看握手 RTT/失败率，再看 CPU 与证书链，最后看复用策略是否合理。
"""


def _body_cubic_bbr(title: str) -> str:
    return """
## 1. 拥塞控制在做什么

在吞吐与延迟之间取平衡：探测带宽/避免拥塞崩溃。

## 2. CUBIC vs BBR 的直觉差别

- CUBIC：偏丢包信号与窗口增长形态。
- BBR：更像“测带宽与 RTT”，目标是靠模型避免排队。

## 3. 排障顺序

先看是否 bufferbloat（排队延迟），再看丢包与重传，最后考虑拥塞控制算法与配置差异。
"""


def _body_cache_line(title: str) -> str:
    return """
## 1. cache line 的工程直觉

CPU 以 cache line 为单位搬运数据；跨 line/伪共享会让性能掉得很“玄学”。

## 2. 常见坑：false sharing

两个线程写不同变量，但落在同一 cache line → cache line 抖动 → 延迟/吞吐下降。

## 3. 排障顺序

先定位热点写变量，再检查结构体布局与 padding，对比 perf 里的 cache miss/remote hit。
"""


def _body_pipeline_flush(title: str) -> str:
    return """
## 1. flush 的直觉：猜错了就要清空流水线

分支预测失败会导致 pipeline flush，代价是浪费多个 cycle。

## 2. 线上表现

branch miss 高 → IPC 下降 → 同样 CPU 利用率下吞吐变差。

## 3. 优化思路

减少不可预测分支、让热路径更直、用表驱动/位运算替代复杂 if。
"""


def _body_fence(title: str) -> str:
    return """
## 1. 为什么需要 fence

编译器/CPU/缓存系统都会重排；fence 提供跨线程可见性的顺序约束。

## 2. 最常见场景：发布-订阅（publish/consume）

先写数据，再写标志位；读侧先读标志位再读数据，需要正确的内存序。

## 3. 排障思路

Bug 往往表现为“偶现”与“只在某些架构/优化级别出现”。优先用成熟原语（atomic/锁）而不是手写 fence。
"""


def _body_io_uring(title: str) -> str:
    return """
## 1. io_uring 的核心：把系统调用批量化

通过 SQ/CQ 环形队列提交与回收 IO，减少 syscall/上下文切换开销。

## 2. 什么时候有效

高并发、小 IO、多 syscall 场景更容易受益。

## 3. 排障顺序

先看是否被文件系统/设备限制（IO 本身慢），再看提交/回收是否成为瓶颈（用户态/内核态交互）。
"""


def _body_storage_merge(title: str) -> str:
    return """
## 1. 写入合并的目标

把随机写“聚合”为顺序写：从日志到段/从 memtable 到 SST，本质是用后台重写换取前台吞吐与稳定。

## 2. 代价与副作用

- 写放大（后台合并重写）
- 空间放大（多版本并存、tombstone）

## 3. 排障顺序

先看后台欠账（compaction/merge backlog），再看写入形态（覆盖写/小写），最后调预算与策略。
"""


def _body_cpu_io(title: str) -> str:
    return """
## 1. CPU-bound vs IO-bound

同样是“变慢”，可能是 CPU 算不动，也可能是 IO/锁/网络在卡。

## 2. 快速判断法

- CPU 利用率高 + IPC 低：可能是 cache/branch/锁。
- IO 延迟分位数抬头：可能是设备/队列/后台任务。

## 3. 排障顺序

先分桶归因（CPU/IO/锁），再针对性做优化。
"""


def _body_ec(title: str) -> str:
    return """
## 1. EC 的直觉

用 K+M 的编码把冗余从“整副本”变成“条带校验”，节省空间但增加计算与修复复杂度。

## 2. 工程关注点

- 小对象放大（条带化带来的读写放大）
- 修复流量与尾延迟

## 3. 排障顺序

先看对象大小分布与条带配置，再看修复频率与带宽预算，最后看编码 CPU 是否成为瓶颈。
"""


def _body_bucket_prefix(title: str) -> str:
    return """
## 1. bucket/prefix 与分区

对象存储常按 bucket/prefix 做分区/路由；热点 prefix 会导致元数据或目录服务倾斜。

## 2. 工程建议

- 让 key 更均匀（hash 前缀/打散）
- 目录服务做分片与缓存

## 3. 排障顺序

先确认热点 prefix，再看元数据服务的 QPS/延迟与缓存命中，最后优化 key 设计或分区策略。
"""


def _body_rpo_rto(title: str) -> str:
    return """
## 1. RPO / RTO 是什么

- RPO：最多能丢多少数据
- RTO：最多能停多久

## 2. 工程权衡

同步复制更小 RPO 但更贵；异步复制吞吐更高但有窗口。

## 3. 排障顺序

先确认业务目标，再把系统拆成：复制链路延迟、故障检测与切换时间、恢复/重建速度。
"""


def _body_quorum(title: str) -> str:
    return """
## 1. quorum 的意义

多数派让系统在部分故障下仍能做出唯一决定（避免双写/脑裂）。

## 2. 常见坑

跨 AZ/跨 Region 的 RTT 会直接影响写入确认与尾延迟。

## 3. 排障顺序

先看 quorum 路径上的延迟分布，再看 leader/副本分布，最后再谈选主与超时参数。
"""


def _body_leader_lease(title: str) -> str:
    return """
## 1. lease 的直觉

用时间窗口减少读路径的共识成本：在 lease 有效期内，leader 可以更快回答读（取决于系统语义）。

## 2. 风险

时钟与网络抖动会影响 lease 的正确性边界；要谨慎定义“读的承诺”。

## 3. 排障顺序

先确认你要的读语义（线性/顺序/最终），再看时钟漂移与 RTT 分布，最后决定是否使用 lease。
"""


def _body_matchindex(title: str) -> str:
    return """
## 1. matchIndex/commitIndex 的直觉

leader 跟踪每个 follower 复制到哪里（matchIndex），多数派达到某个 index 才能提交（commitIndex）。

## 2. 线上现象

慢 follower 会拖慢 commit 推进（取决于实现与配置），并造成 tail latency 抖动。

## 3. 排障顺序

先定位慢副本（网络/磁盘），再看日志复制 backlog，最后看是否需要调整副本布局与限速策略。
"""


def _body_joint_consensus(title: str) -> str:
    return """
## 1. joint consensus 解决什么

成员变更时避免“新旧配置各自形成多数派”，用联合多数派保证安全。

## 2. 工程关注点

成员变更是高风险操作：需要明确状态机、回滚策略与观测告警。
"""


def _body_split_brain(title: str) -> str:
    return """
## 1. 脑裂是什么：同一时刻出现两个“主”

常见根因：网络分区 + 错误的主选举/租约边界/仲裁缺失。

## 2. 工程上怎么避免

- 明确仲裁：quorum/多数派/外部仲裁
- 明确 lease 边界与时钟假设
- 降低误判：心跳与超时要结合 RTT 分布

## 3. 观测与排障

优先看：选主频率、心跳 RTT 分布、分区事件（丢包/重传/抖动），以及是否出现双写迹象。
"""


def _body_linearizability(title: str) -> str:
    return """
## 1. 线性一致性的直觉：像“单机按时间排序”

从客户端视角：所有操作看起来在某个全局时间线中依次发生。

## 2. 你为什么会关心

涉及强读、交易、配置变更、幂等与去重时，语义边界非常关键。

## 3. 验证与排障

先把语义说清楚（读写承诺），再看实现是否满足（leader 路径、quorum、读屏障/lease）。
"""


def _body_timeout_retry(title: str) -> str:
    return """
## 1. 为什么超时 + 重试会放大流量

一次请求慢 → 触发重试 → 并发上升 → 队列更长 → 更慢 → 更多超时（正反馈）。

## 2. 工程解法（优先级顺序）

1. **限流/熔断**：先阻止雪崩扩散
2. **退避 + 抖动**：避免同步重试
3. **幂等与去重**：避免重试产生副作用

## 3. 观测指标

超时率、重试率、入队等待时间、P99、以及重试导致的额外 QPS。
"""


def _body_object_metadata(title: str) -> str:
    return """
## 1. 元数据服务在对象存储中的位置

payload 放数据节点，元数据负责：key→location/version/etag，以及目录/索引能力。

## 2. 两条链路

- GET：单 key 元数据命中 → 定位数据
- LIST：目录/前缀索引（更容易滞后，且更容易热点倾斜）

## 3. 排障顺序

先看元数据 QPS/延迟与缓存命中，再看热点 key/prefix 与分区策略，最后看一致性与版本化设计。
"""


def _body_generic_post(title: str) -> str:
    return """
## 1. 先把语义/模型说清楚

- 这件事的“成功”到底意味着什么？
- 哪些边界条件会让你看到反直觉现象？

## 2. 你应该先看哪些指标

先找能证明因果的中间量（队列/欠账/命中率/重传率等），不要只看平均值。

## 3. 最小排障顺序

1. 定义承诺（语义）
2. 验证事实（指标）
3. 再做调整（参数/预算/架构）
"""


def main() -> int:
    posts = sorted(POSTS_DIR.glob("*.md"))
    to_upgrade = []
    for p in posts:
        text = p.read_text(encoding="utf-8")
        if TEMPLATE_MARKER in text:
            to_upgrade.append(p)

    diagrams_needed: Dict[str, str] = {}
    upgraded = 0

    for p in to_upgrade:
        text = p.read_text(encoding="utf-8")
        fm, _ = split_front_matter(text)
        title = extract_title(fm)
        topic = topic_from_filename(p)
        plan = plan_for_post(topic, title)

        # Track diagrams that might not exist yet.
        diag_path = DIAGRAMS_DIR / plan.diagram
        if not diag_path.exists():
            diagrams_needed[plan.diagram] = title or plan.diagram

        new_body = build_body(title, plan.diagram, plan.body)
        p.write_text(fm + "\n" + new_body, encoding="utf-8")
        upgraded += 1

    # create missing diagrams (simple placeholders that are stable and reusable)
    ensure_diagrams(diagrams_needed)

    print(f"Upgraded {upgraded} posts.")
    print(f"Created {sum(1 for k in diagrams_needed if (DIAGRAMS_DIR / k).exists())} missing diagrams (if any).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

