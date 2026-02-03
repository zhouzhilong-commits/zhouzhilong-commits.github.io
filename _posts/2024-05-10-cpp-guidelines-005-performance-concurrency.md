---
layout: single
title: "C++ Core Guidelines 阅读笔记（5）：性能与并发"
series: cpp
permalink: /cpp-guidelines-005-performance-concurrency/
tags: [C++, 编程语言, C++ Core Guidelines]
---

## 前言

本文是 C++ Core Guidelines 阅读笔记的第五篇，重点讨论性能优化和并发编程的规范。C++ 的优势在于性能，但需要正确使用才能发挥出来。

## 1. 性能优化原则

性能优化需要遵循正确的原则，避免过早优化和错误优化。

### 1.1 先测量，再优化

性能优化的黄金法则：先测量，找到真正的瓶颈，再优化。

```cpp
// 好的：先测量性能
void optimize() {
    auto start = std::chrono::high_resolution_clock::now();
    process_data();
    auto end = std::chrono::high_resolution_clock::now();
    
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(
        end - start);
    std::cout << "Time: " << duration.count() << " us\n";
    // 分析性能瓶颈，找到真正的热点
}

// 不好：过早优化
void optimize() {
    // 没有测量就优化，可能优化了错误的地方
    // 浪费时间和精力，代码变得更复杂
}
```

### 1.2 避免不必要的拷贝

拷贝是常见的性能瓶颈，应该尽量避免：

```cpp
// 好的：使用引用
void process(const std::vector<int>& vec);
// 无拷贝开销

// 不好：值传递
void process(std::vector<int> vec);  
// 拷贝整个 vector，开销大
```

### 1.3 使用移动语义

移动语义可以避免昂贵的拷贝操作：

```cpp
// 好的：移动语义
std::vector<int> create_data() {
    std::vector<int> data;
    // ...
    return data;  // 移动，不拷贝
}

// 不好：不必要的拷贝
std::vector<int> data = create_data();  
// 可能拷贝（如果编译器没有优化）
```

## 2. 内存管理性能

### 2.1 预分配容器空间

```cpp
// 好的：预分配空间
std::vector<int> vec;
vec.reserve(1000);  // 避免多次重新分配

for (int i = 0; i < 1000; ++i) {
    vec.push_back(i);
}

// 不好：动态分配
std::vector<int> vec;
for (int i = 0; i < 1000; ++i) {
    vec.push_back(i);  // 可能多次重新分配
}
```

### 2.2 使用对象池

```cpp
// 好的：对象池
class ObjectPool {
private:
    std::vector<std::unique_ptr<Object>> pool_;
public:
    std::unique_ptr<Object> acquire() {
        if (pool_.empty()) {
            return std::make_unique<Object>();
        }
        auto obj = std::move(pool_.back());
        pool_.pop_back();
        return obj;
    }
    void release(std::unique_ptr<Object> obj) {
        pool_.push_back(std::move(obj));
    }
};
```

## 3. 算法选择

### 3.1 选择合适的算法

```cpp
// 好的：选择合适的算法
std::sort(vec.begin(), vec.end());  // O(n log n)

// 如果只需要部分排序
std::partial_sort(vec.begin(), vec.begin() + 10, vec.end());

// 如果只需要第 k 大元素
std::nth_element(vec.begin(), vec.begin() + k, vec.end());
```

### 3.2 避免不必要的算法调用

```cpp
// 好的：直接访问
if (!vec.empty()) {
    int first = vec[0];
}

// 不好：使用算法
auto it = std::find_if(vec.begin(), vec.end(), [](int x) { return true; });
if (it != vec.end()) {
    int first = *it;
}
```

## 4. 并发编程

### 4.1 使用标准库线程

```cpp
// 好的：标准库线程
#include <thread>

void worker() {
    // 工作逻辑
}

std::thread t(worker);
t.join();
```

### 4.2 使用互斥锁保护共享数据

```cpp
// 好的：使用互斥锁
std::mutex mtx;
int shared_data = 0;

void increment() {
    std::lock_guard<std::mutex> lock(mtx);
    ++shared_data;
}

// 不好：无保护访问
int shared_data = 0;

void increment() {
    ++shared_data;  // 数据竞争
}
```

### 4.3 避免死锁

```cpp
// 好的：按固定顺序获取锁
void process() {
    std::lock(mtx1, mtx2);  // 同时获取多个锁
    std::lock_guard<std::mutex> lock1(mtx1, std::adopt_lock);
    std::lock_guard<std::mutex> lock2(mtx2, std::adopt_lock);
}

// 不好：不同顺序获取锁
void process1() {
    mtx1.lock();
    mtx2.lock();  // 可能死锁
}

void process2() {
    mtx2.lock();
    mtx1.lock();  // 不同顺序
}
```

## 5. 原子操作

### 5.1 使用原子类型

```cpp
// 好的：原子类型
std::atomic<int> counter{0};

void increment() {
    counter.fetch_add(1);
}

// 不好：非原子操作
int counter = 0;

void increment() {
    ++counter;  // 数据竞争
}
```

### 5.2 内存序

```cpp
// 好的：明确内存序
std::atomic<int> data{0};
std::atomic<bool> ready{false};

// 线程 1
data.store(42, std::memory_order_release);
ready.store(true, std::memory_order_release);

// 线程 2
if (ready.load(std::memory_order_acquire)) {
    int value = data.load(std::memory_order_acquire);
}
```

## 6. 条件变量

### 6.1 使用条件变量同步

```cpp
// 好的：条件变量
std::condition_variable cv;
std::mutex mtx;
bool ready = false;

void producer() {
    std::lock_guard<std::mutex> lock(mtx);
    ready = true;
    cv.notify_one();
}

void consumer() {
    std::unique_lock<std::mutex> lock(mtx);
    cv.wait(lock, []{ return ready; });
}
```

## 7. 异步编程

### 7.1 使用 std::async

```cpp
// 好的：std::async
auto future = std::async(std::launch::async, []() {
    return compute_result();
});

int result = future.get();
```

### 7.2 使用 std::future

```cpp
// 好的：std::future
std::promise<int> promise;
auto future = promise.get_future();

std::thread t([&promise]() {
    promise.set_value(42);
});

int result = future.get();
t.join();
```

## 8. 性能测量

### 8.1 使用性能分析工具

```cpp
// 使用 perf 分析
// perf record ./program
// perf report

// 使用 gprof
// 编译时添加 -pg
// gprof ./program gmon.out
```

### 8.2 基准测试

```cpp
// 好的：基准测试
void benchmark() {
    const int iterations = 1000000;
    
    auto start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        process();
    }
    auto end = std::chrono::high_resolution_clock::now();
    
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(
        end - start);
    std::cout << "Average: " << duration.count() / iterations << " us\n";
}
```

## 9. 最佳实践

### 9.1 性能优化检查清单

1. **先测量，再优化**
2. **避免不必要的拷贝**
3. **使用移动语义**
4. **预分配容器空间**
5. **选择合适的算法**
6. **使用并发提高性能**
7. **保护共享数据**
8. **避免死锁**

### 9.2 常见性能问题

```cpp
// 问题 1：不必要的拷贝
void process(std::vector<int> vec);  // 拷贝开销

// 问题 2：频繁内存分配
for (int i = 0; i < n; ++i) {
    vec.push_back(i);  // 可能多次重新分配
}

// 问题 3：数据竞争
int counter = 0;
void increment() {
    ++counter;  // 多线程不安全
}
```

## 11. 实际工程案例

### 11.1 案例：性能优化

**问题**：程序运行慢

```cpp
// 原始代码：性能差
void process_data(std::vector<int> data) {  // 拷贝
    for (int x : data) {  // 范围 for
        process(x);
    }
}
```

**改进**：优化参数传递和算法

```cpp
// 改进代码：性能好
void process_data(const std::vector<int>& data) {  // 引用传递
    std::for_each(data.begin(), data.end(), process);  // 算法
}
```

### 11.2 案例：并发优化

**问题**：单线程处理慢

```cpp
// 原始代码：单线程
void process_all(const std::vector<Data>& items) {
    for (const auto& item : items) {
        process(item);  // 串行处理
    }
}
```

**改进**：使用多线程

```cpp
// 改进代码：多线程
void process_all(const std::vector<Data>& items) {
    std::vector<std::thread> threads;
    const size_t num_threads = std::thread::hardware_concurrency();
    
    for (size_t i = 0; i < num_threads; ++i) {
        threads.emplace_back([&items, i, num_threads]() {
            for (size_t j = i; j < items.size(); j += num_threads) {
                process(items[j]);
            }
        });
    }
    
    for (auto& t : threads) {
        t.join();
    }
}
```

## 12. 性能分析工具

### 12.1 性能分析工具


### 12.2 性能指标

```cpp
// 关键性能指标
struct PerformanceMetrics {
    double cpu_time;      // CPU 时间
    double wall_time;     // 墙上时钟时间
    size_t memory_usage;  // 内存使用
    size_t cache_misses; // 缓存未命中
    size_t branch_misses; // 分支预测失败
};
```

## 13. 并发设计模式

### 13.1 生产者-消费者模式


### 13.2 线程池模式


## 14. 最佳实践检查清单

### 14.1 性能优化检查清单

1. **先测量，再优化**
2. **避免不必要的拷贝**
3. **使用移动语义**
4. **预分配容器空间**
5. **选择合适的算法**
6. **使用并发提高性能**
7. **保护共享数据**
8. **避免死锁**

### 14.2 并发编程检查清单

1. **使用互斥锁保护共享数据**
2. **避免数据竞争**
3. **避免死锁**
4. **使用原子操作进行简单同步**
5. **使用条件变量进行线程同步**
6. **合理使用线程池**

## 15. 小结

性能优化和并发编程需要遵循正确的原则和模式。

**核心要点**：
- **性能优化原则**：先测量再优化、避免不必要的拷贝、使用移动语义
- **内存管理性能**：预分配空间、使用对象池
- **算法选择**：选择合适的算法、避免不必要的调用
- **并发编程**：使用标准库线程、互斥锁保护数据、避免死锁
- **原子操作**：使用原子类型、明确内存序
- **条件变量**：使用条件变量同步线程
- **异步编程**：使用 std::async 和 std::future
- **性能测量**：使用性能分析工具、基准测试

遵循这些规范，可以写出高性能、线程安全的 C++ 代码。
