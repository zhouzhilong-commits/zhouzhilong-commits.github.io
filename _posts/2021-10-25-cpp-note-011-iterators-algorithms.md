---
layout: single
title: "C++ 笔记：迭代器与算法：STL 算法库的使用"
series: cpp
permalink: /cpp-note-011-iterators-algorithms/
tags: [C++, 编程语言]
---

## 前言

STL 算法库是 C++ 标准库的核心，提供了丰富的通用算法。理解迭代器和算法的配合使用，是写出高效、优雅 C++ 代码的关键。本文将从迭代器分类、常用算法、自定义算法等多个维度深入解析 STL 算法库，帮助读者全面理解这一重要组件。

## 1. 迭代器基础

### 1.1 迭代器分类

迭代器分为五类，从弱到强：

- **输入迭代器（Input Iterator）**：只能读取，只能向前
- **输出迭代器（Output Iterator）**：只能写入，只能向前
- **前向迭代器（Forward Iterator）**：可以读写，只能向前
- **双向迭代器（Bidirectional Iterator）**：可以向前向后
- **随机访问迭代器（Random Access Iterator）**：可以任意跳转

### 1.2 迭代器特性

```cpp
#include <iterator>

// 获取迭代器类型
using iter_type = std::iterator_traits<std::vector<int>::iterator>::iterator_category;

// 检查迭代器类型
static_assert(std::is_same_v<iter_type, std::random_access_iterator_tag>);
```

## 2. 常用算法

### 2.1 查找算法

```cpp
#include <algorithm>

std::vector<int> vec = {1, 2, 3, 4, 5};

// find：查找值
auto it = std::find(vec.begin(), vec.end(), 3);

// find_if：查找满足条件的元素
auto it2 = std::find_if(vec.begin(), vec.end(), 
                        [](int x) { return x > 3; });

// binary_search：二分查找（需要有序）
bool found = std::binary_search(vec.begin(), vec.end(), 3);
```

### 2.2 计数算法

```cpp
// count：计数等于值的元素
int count = std::count(vec.begin(), vec.end(), 3);

// count_if：计数满足条件的元素
int count_if = std::count_if(vec.begin(), vec.end(),
                             [](int x) { return x > 3; });
```

### 2.3 变换算法

```cpp
// transform：转换元素
std::vector<int> result;
std::transform(vec.begin(), vec.end(), std::back_inserter(result),
               [](int x) { return x * 2; });

// for_each：对每个元素执行操作
std::for_each(vec.begin(), vec.end(), 
              [](int& x) { x *= 2; });
```

### 2.4 排序算法

```cpp
// sort：排序
std::sort(vec.begin(), vec.end());

// partial_sort：部分排序
std::partial_sort(vec.begin(), vec.begin() + 3, vec.end());

// nth_element：找到第 n 大的元素
std::nth_element(vec.begin(), vec.begin() + 2, vec.end());
```

## 3. 算法与迭代器配合

### 3.1 输入/输出迭代器

```cpp
// 从输入流读取
std::vector<int> vec;
std::copy(std::istream_iterator<int>(std::cin),
          std::istream_iterator<int>(),
          std::back_inserter(vec));

// 输出到流
std::copy(vec.begin(), vec.end(),
          std::ostream_iterator<int>(std::cout, " "));
```

### 3.2 插入迭代器

```cpp
// back_inserter：尾部插入
std::vector<int> result;
std::copy(vec.begin(), vec.end(), std::back_inserter(result));

// front_inserter：头部插入（需要支持 push_front）
std::list<int> lst;
std::copy(vec.begin(), vec.end(), std::front_inserter(lst));

// inserter：指定位置插入
std::set<int> s;
std::copy(vec.begin(), vec.end(), std::inserter(s, s.begin()));
```

## 4. 算法组合

### 4.1 管道式编程

```cpp
// 组合多个算法
std::vector<int> vec = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

// 过滤、转换、收集
std::vector<int> result;
std::copy_if(vec.begin(), vec.end(), std::back_inserter(result),
             [](int x) { return x % 2 == 0; });
std::transform(result.begin(), result.end(), result.begin(),
               [](int x) { return x * x; });
```

### 4.2 范围算法（C++20）

```cpp
#include <ranges>

// 使用范围视图
auto even_squares = vec 
    | std::views::filter([](int x) { return x % 2 == 0; })
    | std::views::transform([](int x) { return x * x; });

for (auto value : even_squares) {
    std::cout << value << " ";
}
```

## 5. 自定义算法

### 5.1 实现通用算法

```cpp
template<typename InputIt, typename UnaryPredicate>
bool all_of(InputIt first, InputIt last, UnaryPredicate pred) {
    for (; first != last; ++first) {
        if (!pred(*first)) {
            return false;
        }
    }
    return true;
}
```

### 5.2 算法特化

```cpp
// 为特定容器类型特化
template<typename T>
void sort_optimized(std::vector<T>& vec) {
    if (vec.size() < 100) {
        // 小数组使用插入排序
        insertion_sort(vec.begin(), vec.end());
    } else {
        // 大数组使用快速排序
        std::sort(vec.begin(), vec.end());
    }
}
```

## 6. 性能考虑

### 6.1 算法复杂度

不同算法有不同的复杂度：

- `std::find`：O(n)
- `std::binary_search`：O(log n)（需要有序）
- `std::sort`：O(n log n)
- `std::nth_element`：O(n)

### 6.2 优化技巧

```cpp
// 预分配空间
std::vector<int> result;
result.reserve(vec.size());  // 避免多次重新分配

// 使用移动语义
std::move(vec.begin(), vec.end(), result.begin());
```

## 7. 实际应用

### 7.1 数据处理管道

```cpp
// 读取、过滤、转换、输出
std::vector<int> data;
std::copy(std::istream_iterator<int>(std::cin),
          std::istream_iterator<int>(),
          std::back_inserter(data));

data.erase(std::remove_if(data.begin(), data.end(),
                          [](int x) { return x < 0; }),
           data.end());

std::transform(data.begin(), data.end(), data.begin(),
               [](int x) { return x * 2; });

std::copy(data.begin(), data.end(),
          std::ostream_iterator<int>(std::cout, "\n"));
```

### 7.2 容器操作

```cpp
// 合并两个有序容器
std::vector<int> vec1 = {1, 3, 5};
std::vector<int> vec2 = {2, 4, 6};
std::vector<int> merged;

std::merge(vec1.begin(), vec1.end(),
           vec2.begin(), vec2.end(),
           std::back_inserter(merged));
```

## 8. 最佳实践

### 8.1 优先使用算法而非循环

```cpp
// 推荐：使用算法
auto it = std::find_if(vec.begin(), vec.end(),
                       [](int x) { return x > 10; });

// 不推荐：手写循环
for (auto it = vec.begin(); it != vec.end(); ++it) {
    if (*it > 10) {
        break;
    }
}
```

### 8.2 使用 Lambda 表达式

```cpp
// Lambda 使算法更灵活
std::sort(vec.begin(), vec.end(),
          [](int a, int b) { return a > b; });  // 降序
```

## 9. 小结

STL 算法库提供了丰富的通用算法，配合迭代器可以实现高效的数据处理。

**核心要点**：
- 理解不同迭代器类型的能力
- 掌握常用算法的使用场景
- 学会组合多个算法
- 注意算法复杂度
- 优先使用算法而非手写循环

掌握 STL 算法库，可以写出更简洁、更高效的 C++ 代码。
