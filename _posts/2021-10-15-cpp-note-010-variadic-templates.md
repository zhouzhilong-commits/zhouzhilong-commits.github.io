---
layout: single
title: "C++ 笔记：可变参数模板：参数包展开与折叠表达式"
series: cpp
permalink: /cpp-note-010-variadic-templates/
tags: [C++, 编程语言]
---

## 前言

可变参数模板是 C++11 引入的强大特性，允许模板接受任意数量的参数。理解可变参数模板不仅是掌握现代 C++ 的关键，更是实现灵活、通用的代码的基础。本文将从参数包、展开规则、折叠表达式等多个维度深入解析可变参数模板，帮助读者全面理解这一重要特性。

## 1. 为什么需要可变参数模板

### 1.1 传统方法的局限性

在 C++11 之前，要实现接受任意数量参数的函数，需要使用：

```cpp
// C 风格：va_list（类型不安全）
void func(int count, ...) {
    va_list args;
    va_start(args, count);
    // 类型不安全，容易出错
    va_end(args);
}

// 函数重载：需要为每个参数数量写一个版本
void print() {}
void print(int a) {}
void print(int a, int b) {}
void print(int a, int b, int c) {}
// ... 需要很多重载
```

### 1.2 可变参数模板的优势

```cpp
// 一个模板函数处理所有情况
template<typename... Args>
void print(Args... args) {
    // 类型安全，编译期确定
}
```

## 2. 参数包基础

### 2.1 模板参数包

```cpp
// 类型参数包
template<typename... Args>
void func(Args... args) {
    // Args 是类型参数包
    // args 是函数参数包
}

// 非类型参数包
template<int... Values>
void func() {
    // Values 是非类型参数包
}
```

### 2.2 参数包的大小

```cpp
template<typename... Args>
void func(Args... args) {
    constexpr size_t count = sizeof...(Args);  // 参数包大小
    constexpr size_t args_count = sizeof...(args);  // 参数包大小
}
```

## 3. 参数包展开

### 3.1 基本展开规则

```cpp
template<typename... Args>
void print(Args... args) {
    // 展开为：print(arg1, arg2, arg3, ...)
    std::cout << args... << "\n";  // 错误：不能直接展开
}
```

### 3.2 递归展开

```cpp
// 终止条件
void print() {
    std::cout << "\n";
}

// 递归展开
template<typename T, typename... Args>
void print(T first, Args... rest) {
    std::cout << first << " ";
    print(rest...);  // 递归展开剩余参数
}

// 使用
print(1, 2.5, "hello", 'c');  // 输出：1 2.5 hello c
```

### 3.3 展开模式

```cpp
template<typename... Args>
void func(Args... args) {
    // 模式展开
    helper(args...);           // 直接展开
    helper((args + 1)...);     // 每个参数加 1
    helper(f(args)...);        // 每个参数应用函数 f
    helper(g(args, 1)...);     // 每个参数调用 g(args, 1)
}
```

## 4. 折叠表达式（C++17）

### 4.1 二元折叠

```cpp
// 左折叠
template<typename... Args>
auto sum_left(Args... args) {
    return (args + ...);  // ((arg1 + arg2) + arg3) + ...
}

// 右折叠
template<typename... Args>
auto sum_right(Args... args) {
    return (... + args);  // arg1 + (arg2 + (arg3 + ...))
}
```

### 4.2 一元折叠

```cpp
// 左折叠（需要初始值）
template<typename... Args>
auto sum_with_init(int init, Args... args) {
    return (init + ... + args);  // init + arg1 + arg2 + ...
}

// 右折叠（需要初始值）
template<typename... Args>
auto sum_with_init_right(Args... args, int init) {
    return (args + ... + init);  // arg1 + arg2 + ... + init
}
```

### 4.3 折叠表达式的应用

```cpp
// 打印所有参数
template<typename... Args>
void print_all(Args... args) {
    ((std::cout << args << " "), ...);  // 逗号折叠
    std::cout << "\n";
}

// 检查所有参数是否满足条件
template<typename... Args>
bool all_positive(Args... args) {
    return ((args > 0) && ...);  // 逻辑与折叠
}
```

## 5. 实际应用场景

### 5.1 完美转发

```cpp
template<typename... Args>
auto make_unique(Args&&... args) {
    return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}
```

### 5.2 函数包装器

```cpp
template<typename Func, typename... Args>
auto call_with_log(Func&& f, Args&&... args) {
    std::cout << "Calling function with " << sizeof...(args) << " arguments\n";
    return std::invoke(std::forward<Func>(f), std::forward<Args>(args)...);
}
```

### 5.3 元组展开

```cpp
template<typename... Args>
void apply_tuple(std::tuple<Args...>&& t, Func&& f) {
    std::apply(std::forward<Func>(f), std::move(t));
}
```

## 6. 常见模式

### 6.1 类型萃取

```cpp
// 检查所有类型是否相同
template<typename T, typename... Args>
struct all_same : std::false_type {};

template<typename T>
struct all_same<T> : std::true_type {};

template<typename T, typename U, typename... Args>
struct all_same<T, U, Args...> 
    : std::conditional_t<std::is_same_v<T, U>, 
                         all_same<T, Args...>, 
                         std::false_type> {};
```

### 6.2 参数验证

```cpp
template<typename... Args>
void safe_func(Args... args) {
    static_assert((std::is_integral_v<Args> && ...), 
                  "All arguments must be integral");
    // 函数实现
}
```

## 7. 性能考虑

### 7.1 编译期展开

可变参数模板在编译期完全展开，运行时无额外开销：

```cpp
// 编译期展开为具体函数调用
print(1, 2, 3);
// 展开为：
// print_impl(1, print_impl(2, print_impl(3, print_impl())))
```

### 7.2 代码膨胀

过多的模板实例化可能导致代码膨胀，需要权衡。

## 8. 最佳实践

### 8.1 使用折叠表达式

优先使用 C++17 的折叠表达式，代码更简洁：

```cpp
// 推荐：折叠表达式
template<typename... Args>
auto sum(Args... args) {
    return (args + ...);
}

// 不推荐：递归展开
template<typename T>
auto sum(T t) { return t; }
template<typename T, typename... Args>
auto sum(T t, Args... args) {
    return t + sum(args...);
}
```

### 8.2 类型约束

使用 `static_assert` 或 Concepts（C++20）约束参数类型。

## 9. 小结

可变参数模板提供了强大的类型安全和灵活性，是现代 C++ 的重要特性。

**核心要点**：
- 参数包可以接受任意数量的参数
- 递归展开是处理参数包的基本方法
- 折叠表达式（C++17）简化了常见操作
- 编译期展开，运行时零开销
- 注意代码膨胀问题

掌握可变参数模板，可以写出更灵活、更通用的 C++ 代码。
