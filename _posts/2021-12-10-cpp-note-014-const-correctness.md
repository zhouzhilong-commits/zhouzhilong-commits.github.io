---
layout: single
title: "C++ 笔记：const 正确性与 mutable：不可变性的设计"
series: cpp
permalink: /cpp-note-014-const-correctness/
tags: [C++, 编程语言]
---

## 前言

const 正确性是 C++ 编程的重要原则，它通过类型系统保证对象的不变性，提高代码的安全性和可维护性。理解 const 的语义、使用场景和 mutable 关键字，是写出健壮 C++ 代码的关键。本文将从 const 语义、使用规则、mutable 应用等多个维度深入解析 const 正确性，帮助读者全面理解这一重要概念。

## 1. const 的语义

### 1.1 const 的基本含义

`const` 表示"不可修改"：

```cpp
const int x = 42;
x = 10;  // 错误：不能修改 const 对象

const int* ptr = &x;  // 指向 const 的指针
*ptr = 10;  // 错误：不能通过 ptr 修改
```

### 1.2 const 的位置

```cpp
const int* p1;        // 指向 const int 的指针
int const* p2;        // 同上，等价写法
int* const p3;        // const 指针，指向 int
const int* const p4;  // const 指针，指向 const int
```

## 2. const 成员函数

### 2.1 const 成员函数的含义

```cpp
class MyClass {
private:
    int value_;
public:
    int get() const {  // const 成员函数
        return value_;  // 不能修改成员变量
    }
    
    void set(int v) {  // 非 const 成员函数
        value_ = v;     // 可以修改成员变量
    }
};
```

### 2.2 const 对象只能调用 const 成员函数

```cpp
const MyClass obj;
int x = obj.get();  // OK：调用 const 成员函数
obj.set(10);       // 错误：不能调用非 const 成员函数
```

## 3. const 正确性的重要性

### 3.1 防止意外修改

```cpp
void process(const std::vector<int>& vec) {
    // vec 是 const 引用，不能修改
    // 保证函数不会意外修改参数
    for (int x : vec) {
        // 处理
    }
}
```

### 3.2 提高代码可读性

```cpp
// const 明确表示函数不会修改对象
int get_value() const;

// 非 const 表示函数可能修改对象
void set_value(int v);
```

## 4. mutable 关键字

### 4.1 mutable 的用途

`mutable` 允许在 const 成员函数中修改成员变量：

```cpp
class Cache {
private:
    mutable int cache_value_;
    mutable bool cache_valid_;
    int compute_expensive() const;
public:
    int get_value() const {
        if (!cache_valid_) {
            cache_value_ = compute_expensive();  // mutable 允许修改
            cache_valid_ = true;
        }
        return cache_value_;
    }
};
```

### 4.2 mutable 的应用场景

```cpp
// 1. 缓存
class ExpensiveComputation {
    mutable std::optional<int> cache_;
public:
    int compute() const {
        if (!cache_) {
            cache_ = do_computation();
        }
        return *cache_;
    }
};

// 2. 互斥锁
class ThreadSafeCounter {
    mutable std::mutex mtx_;
    int count_;
public:
    int get() const {
        std::lock_guard<std::mutex> lock(mtx_);  // mutable 允许锁定
        return count_;
    }
};
```

## 5. const 与指针

### 5.1 指向 const 的指针

```cpp
const int* ptr;  // 指向 const int
int x = 42;
ptr = &x;
// *ptr = 10;  // 错误：不能通过 ptr 修改
```

### 5.2 const 指针

```cpp
int* const ptr = &x;  // const 指针
// ptr = &y;  // 错误：不能修改指针本身
*ptr = 10;  // OK：可以修改指向的对象
```

### 5.3 const 引用

```cpp
const int& ref = x;  // const 引用
// ref = 10;  // 错误：不能通过 ref 修改
```

## 6. const 与函数参数

### 6.1 值传递

```cpp
void func(int x) {  // 拷贝，不需要 const
    // x 是局部变量，修改不影响原对象
}
```

### 6.2 引用传递

```cpp
void func(const int& x) {  // const 引用
    // 不能修改 x，避免意外修改原对象
}

void modify(int& x) {  // 非 const 引用
    x = 10;  // 明确表示会修改参数
}
```

### 6.3 指针传递

```cpp
void func(const int* ptr) {  // 指向 const 的指针
    // 不能通过 ptr 修改指向的对象
}

void modify(int* ptr) {  // 非 const 指针
    *ptr = 10;  // 明确表示会修改指向的对象
}
```

## 7. const 与返回值

### 7.1 返回 const 值

```cpp
const int get_value() {
    return 42;
}

// 通常不需要，因为返回值是临时对象
```

### 7.2 返回 const 引用

```cpp
class Container {
private:
    std::vector<int> data_;
public:
    const int& get(size_t index) const {
        return data_[index];  // 返回 const 引用，防止修改
    }
};
```

## 8. const 正确性的实践

### 8.1 默认使用 const

```cpp
// 好的实践：默认使用 const
void process(const std::vector<int>& vec) const;

// 只在需要修改时才使用非 const
void modify(std::vector<int>& vec);
```

### 8.2 const 成员函数的重载

```cpp
class Array {
private:
    int* data_;
public:
    int& operator[](size_t index) {
        return data_[index];
    }
    
    const int& operator[](size_t index) const {
        return data_[index];
    }
};
```

## 9. 常见错误

### 9.1 忘记 const

```cpp
class MyClass {
public:
    int get() {  // 应该是 const
        return value_;
    }
};

const MyClass obj;
obj.get();  // 错误：不能调用非 const 成员函数
```

### 9.2 过度使用 mutable

```cpp
// 不好：过度使用 mutable
class Bad {
    mutable int value_;  // 不应该用 mutable
public:
    int get() const {
        return value_;
    }
};
```

## 10. 小结

const 正确性通过类型系统保证对象的不变性，提高代码的安全性和可维护性。

**核心要点**：
- const 表示不可修改
- const 成员函数不能修改成员变量
- const 对象只能调用 const 成员函数
- mutable 允许在 const 函数中修改特定成员
- 默认使用 const，只在需要修改时使用非 const

掌握 const 正确性，可以写出更安全、更健壮的 C++ 代码。
