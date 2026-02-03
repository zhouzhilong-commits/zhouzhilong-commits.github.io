---
layout: single
title: "C++ 笔记：并发编程基础：线程与同步"
series: cpp
permalink: /cpp-note-007-concurrency-basics/
tags: [C++, 编程语言]
---

## 前言

并发编程是现代 C++ 的重要特性，C++11 引入了标准线程库，使得多线程编程变得更加安全和高效。理解并发编程不仅是掌握现代 C++ 的关键，更是写出高性能、可扩展代码的基础。本文将从线程创建、同步原语、数据竞争等多个维度深入解析 C++ 并发编程，帮助读者全面理解这一重要特性。

## 1. 为什么需要并发编程

### 1.1 并发编程的优势

- **性能提升**：利用多核 CPU 并行计算
- **响应性**：后台任务不阻塞主线程
- **资源利用**：充分利用系统资源

### 1.2 并发编程的挑战

- **数据竞争**：多个线程同时访问共享数据
- **死锁**：线程相互等待导致程序卡死
- **竞态条件**：执行顺序不确定导致结果错误

## 2. 线程基础

### 2.1 创建线程

```cpp
#include <thread>
#include <iostream>

void hello() {
    std::cout << "Hello from thread\n";
}

int main() {
    std::thread t(hello);
    t.join();  // 等待线程结束
    return 0;
}
```

### 2.2 线程管理

```cpp
std::thread t1(func1);
std::thread t2(func2);

// 等待线程完成
t1.join();
t2.join();

// 或分离线程（不等待）
// t1.detach();
```

## 3. 互斥锁与数据保护

### 3.1 std::mutex

```cpp
#include <mutex>

std::mutex mtx;
int shared_data = 0;

void increment() {
    std::lock_guard<std::mutex> lock(mtx);
    ++shared_data;
}
```

### 3.2 锁的类型

- **std::mutex**：基本互斥锁
- **std::recursive_mutex**：可重入互斥锁
- **std::shared_mutex**：读写锁（C++17）

## 4. 条件变量

### 4.1 生产者-消费者模式

```cpp
std::condition_variable cv;
std::mutex mtx;
std::queue<int> queue;

void producer() {
    std::unique_lock<std::mutex> lock(mtx);
    queue.push(42);
    cv.notify_one();
}

void consumer() {
    std::unique_lock<std::mutex> lock(mtx);
    cv.wait(lock, []{ return !queue.empty(); });
    int value = queue.front();
    queue.pop();
}
```

## 5. 原子操作

### 5.1 std::atomic

```cpp
#include <atomic>

std::atomic<int> counter{0};

void increment() {
    counter.fetch_add(1);  // 原子操作
}
```

### 5.2 内存序

```cpp
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

## 6. 线程池模式

### 6.1 基本线程池

```cpp
class ThreadPool {
private:
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex queue_mutex_;
    std::condition_variable condition_;
    bool stop_;

public:
    ThreadPool(size_t threads);
    ~ThreadPool();
    void enqueue(std::function<void()> task);
};
```

## 7. 常见问题与解决方案

### 7.1 死锁预防

- 按固定顺序获取锁
- 使用 `std::lock` 同时获取多个锁
- 避免在持有锁时调用未知代码

### 7.2 数据竞争避免

- 使用互斥锁保护共享数据
- 使用原子操作进行简单操作
- 尽量减少共享数据

## 8. 性能考虑

### 8.1 锁的粒度

```cpp
// 不好：锁粒度太大
{
    std::lock_guard<std::mutex> lock(mtx);
    // 大量不需要保护的操作
    process_data();
    // 只有这里需要保护
    update_shared();
}

// 好：锁粒度小
process_data();  // 不需要锁
{
    std::lock_guard<std::mutex> lock(mtx);
    update_shared();  // 只需要保护这里
}
```

### 8.2 无锁编程

对于简单操作，使用原子操作可以避免锁的开销：

```cpp
// 使用原子操作，无锁
std::atomic<int> counter{0};
counter.fetch_add(1);

// vs 使用锁
std::mutex mtx;
int counter = 0;
{
    std::lock_guard<std::mutex> lock(mtx);
    ++counter;
}
```

## 9. 小结

C++ 并发编程提供了强大的多线程支持，但需要仔细处理同步和数据竞争问题。

**核心要点**：
- 使用 `std::thread` 创建线程
- 使用互斥锁保护共享数据
- 使用条件变量进行线程间通信
- 使用原子操作进行简单同步
- 避免死锁和数据竞争

掌握并发编程，可以写出高性能、可扩展的 C++ 代码。
