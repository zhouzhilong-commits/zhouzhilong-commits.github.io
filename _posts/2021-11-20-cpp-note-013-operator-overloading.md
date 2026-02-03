---
layout: single
title: "C++ 笔记：运算符重载：自定义类型的行为"
series: cpp
permalink: /cpp-note-013-operator-overloading/
tags: [C++, 编程语言]
---

## 前言

运算符重载允许为自定义类型定义运算符的行为，使代码更直观、更易读。理解运算符重载的规则、最佳实践和常见陷阱，是写出优雅 C++ 代码的关键。本文将从重载规则、实现方式、常见模式等多个维度深入解析运算符重载，帮助读者全面理解这一重要特性。

## 1. 为什么需要运算符重载

### 1.1 使代码更直观

```cpp
// 没有运算符重载
Complex a(1, 2);
Complex b(3, 4);
Complex c = a.add(b);  // 不够直观

// 有运算符重载
Complex c = a + b;  // 更直观
```

### 1.2 与标准库类型一致

标准库大量使用运算符重载：

```cpp
std::string s1 = "hello";
std::string s2 = "world";
std::string s3 = s1 + s2;  // 运算符重载

std::vector<int> v1 = {1, 2, 3};
int value = v1[0];  // 运算符重载
```

## 2. 可重载的运算符

### 2.1 可以重载的运算符

大部分运算符可以重载，但以下不能：

- `.`（成员访问）
- `.*`（成员指针访问）
- `::`（作用域解析）
- `?:`（三元运算符）
- `sizeof`
- `typeid`

### 2.2 运算符分类

```cpp
// 算术运算符
+ - * / % 

// 关系运算符
== != < > <= >=

// 逻辑运算符
&& || !

// 赋值运算符
= += -= *= /=

// 下标运算符
[]

// 函数调用运算符
()

// 类型转换运算符
operator Type()
```

## 3. 成员函数 vs 友元函数

### 3.1 成员函数重载

```cpp
class Complex {
private:
    double real_, imag_;
public:
    Complex operator+(const Complex& other) const {
        return Complex(real_ + other.real_, imag_ + other.imag_);
    }
    
    Complex& operator+=(const Complex& other) {
        real_ += other.real_;
        imag_ += other.imag_;
        return *this;
    }
};
```

### 3.2 友元函数重载

```cpp
class Complex {
    friend Complex operator+(const Complex& a, const Complex& b);
    friend std::ostream& operator<<(std::ostream& os, const Complex& c);
};

Complex operator+(const Complex& a, const Complex& b) {
    return Complex(a.real_ + b.real_, a.imag_ + b.imag_);
}

std::ostream& operator<<(std::ostream& os, const Complex& c) {
    os << c.real_ << "+" << c.imag_ << "i";
    return os;
}
```

## 4. 常见运算符重载

### 4.1 赋值运算符

```cpp
class MyClass {
private:
    int* data_;
    size_t size_;
public:
    // 拷贝赋值
    MyClass& operator=(const MyClass& other) {
        if (this != &other) {
            delete[] data_;
            size_ = other.size_;
            data_ = new int[size_];
            std::copy(other.data_, other.data_ + size_, data_);
        }
        return *this;
    }
    
    // 移动赋值（C++11）
    MyClass& operator=(MyClass&& other) noexcept {
        if (this != &other) {
            delete[] data_;
            data_ = other.data_;
            size_ = other.size_;
            other.data_ = nullptr;
            other.size_ = 0;
        }
        return *this;
    }
};
```

### 4.2 下标运算符

```cpp
class Array {
private:
    int* data_;
    size_t size_;
public:
    int& operator[](size_t index) {
        return data_[index];
    }
    
    const int& operator[](size_t index) const {
        return data_[index];
    }
};
```

### 4.3 函数调用运算符

```cpp
class Functor {
public:
    int operator()(int x, int y) const {
        return x + y;
    }
};

// 使用
Functor f;
int result = f(1, 2);  // 调用 operator()
```

### 4.4 类型转换运算符

```cpp
class Rational {
private:
    int num_, den_;
public:
    operator double() const {
        return static_cast<double>(num_) / den_;
    }
    
    explicit operator bool() const {  // explicit 避免意外转换
        return num_ != 0;
    }
};
```

## 5. 运算符重载规则

### 5.1 保持语义一致性

```cpp
// 好的设计：+ 和 += 语义一致
Complex operator+(const Complex& a, const Complex& b);
Complex& operator+=(Complex& a, const Complex& b);

// 通常实现为：
Complex operator+(const Complex& a, const Complex& b) {
    Complex result = a;
    result += b;  // 复用 +=
    return result;
}
```

### 5.2 返回类型

```cpp
// 赋值运算符返回引用
MyClass& operator=(const MyClass& other);

// 算术运算符返回新对象
Complex operator+(const Complex& a, const Complex& b);

// 关系运算符返回 bool
bool operator==(const Complex& a, const Complex& b);
```

## 6. 常见陷阱

### 6.1 自赋值检查

```cpp
MyClass& operator=(const MyClass& other) {
    if (this != &other) {  // 必须检查
        // 赋值逻辑
    }
    return *this;
}
```

### 6.2 const 正确性

```cpp
class Array {
public:
    int& operator[](size_t index);        // 非 const 版本
    const int& operator[](size_t index) const;  // const 版本
};
```

### 6.3 避免过度重载

不要重载不常用的运算符，保持代码可读性。

## 7. 实际应用

### 7.1 智能指针

```cpp
template<typename T>
class SmartPtr {
private:
    T* ptr_;
public:
    T& operator*() const { return *ptr_; }
    T* operator->() const { return ptr_; }
    explicit operator bool() const { return ptr_ != nullptr; }
};
```

### 7.2 迭代器

```cpp
class Iterator {
private:
    int* ptr_;
public:
    int& operator*() const { return *ptr_; }
    Iterator& operator++() { ++ptr_; return *this; }
    bool operator!=(const Iterator& other) const {
        return ptr_ != other.ptr_;
    }
};
```

## 8. 最佳实践

### 8.1 遵循惯例

```cpp
// 算术运算符通常返回新对象
Complex operator+(const Complex& a, const Complex& b);

// 复合赋值运算符返回引用
Complex& operator+=(Complex& a, const Complex& b);

// 关系运算符返回 bool
bool operator==(const Complex& a, const Complex& b);
```

### 8.2 使用 noexcept

```cpp
// 移动操作应该标记 noexcept
MyClass& operator=(MyClass&& other) noexcept;
```

## 9. 小结

运算符重载使自定义类型可以像内置类型一样使用，提高代码可读性。

**核心要点**：
- 保持运算符语义一致性
- 正确实现拷贝和移动赋值
- 注意 const 正确性
- 避免过度重载
- 遵循 C++ 惯例

掌握运算符重载，可以设计出更直观、更易用的 C++ 类型。
