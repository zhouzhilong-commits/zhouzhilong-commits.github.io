---
layout: single
title: "C++ 笔记：多态与虚函数：运行时类型识别"
series: cpp
permalink: /cpp-note-012-polymorphism-virtual/
tags: [C++, 编程语言]
---

## 前言

多态是面向对象编程的核心特性，C++ 通过虚函数实现运行时多态。理解虚函数的工作原理、虚函数表、以及多态的实现机制，是掌握 C++ 面向对象编程的关键。本文将从虚函数、虚函数表、多态实现等多个维度深入解析，帮助读者全面理解这一重要特性。

## 1. 什么是多态

### 1.1 多态的类型

C++ 支持两种多态：

- **编译期多态**：函数重载、模板特化
- **运行时多态**：虚函数、继承

### 1.2 运行时多态示例

```cpp
class Shape {
public:
    virtual void draw() const {
        std::cout << "Drawing a shape\n";
    }
    virtual ~Shape() = default;
};

class Circle : public Shape {
public:
    void draw() const override {
        std::cout << "Drawing a circle\n";
    }
};

void draw_shape(const Shape& shape) {
    shape.draw();  // 运行时多态
}

// 使用
Circle circle;
draw_shape(circle);  // 输出：Drawing a circle
```

## 2. 虚函数机制

### 2.1 虚函数声明

```cpp
class Base {
public:
    virtual void func() {
        std::cout << "Base::func()\n";
    }
    
    virtual ~Base() = default;  // 虚析构函数
};

class Derived : public Base {
public:
    void func() override {  // C++11: override 关键字
        std::cout << "Derived::func()\n";
    }
};
```

### 2.2 override 和 final

```cpp
class Base {
public:
    virtual void func() {}
    virtual void func2() final {}  // 禁止重写
};

class Derived : public Base {
public:
    void func() override {}  // 明确表示重写
    // void func2() {}  // 错误：func2 是 final
};
```

## 3. 虚函数表（vtable）

### 3.1 vtable 的工作原理

每个包含虚函数的类都有一个虚函数表：

```cpp
class Base {
public:
    virtual void func1() {}
    virtual void func2() {}
    int data;
};

// Base 的 vtable：
// [0] -> Base::func1
// [1] -> Base::func2

class Derived : public Base {
public:
    void func1() override {}
    // func2 继承自 Base
};

// Derived 的 vtable：
// [0] -> Derived::func1  (重写)
// [1] -> Base::func2     (继承)
```

### 3.2 对象布局

```cpp
// Base 对象布局：
// [vptr] -> 指向 Base::vtable
// [data] -> int

// Derived 对象布局：
// [vptr] -> 指向 Derived::vtable
// [Base::data] -> int
// [Derived::data] -> int (如果有)
```

## 4. 虚函数调用

### 4.1 调用机制

```cpp
Base* ptr = new Derived();
ptr->func();  // 通过 vtable 调用 Derived::func()

// 等价于：
// 1. 获取对象的 vptr
// 2. 通过 vptr 找到 vtable
// 3. 在 vtable 中找到 func 的地址
// 4. 调用该地址的函数
```

### 4.2 性能开销

虚函数调用有额外开销：

- **间接调用**：需要通过 vptr 和 vtable
- **无法内联**：编译器通常无法内联虚函数
- **缓存不友好**：vtable 查找可能造成缓存未命中

## 5. 纯虚函数与抽象类

### 5.1 纯虚函数

```cpp
class AbstractShape {
public:
    virtual void draw() const = 0;  // 纯虚函数
    virtual ~AbstractShape() = default;
};

// 不能实例化抽象类
// AbstractShape shape;  // 错误
```

### 5.2 接口类

```cpp
// 接口：只有纯虚函数
class Drawable {
public:
    virtual void draw() const = 0;
    virtual ~Drawable() = default;
};

class Circle : public Drawable {
public:
    void draw() const override {
        // 实现
    }
};
```

## 6. 虚析构函数

### 6.1 为什么需要虚析构函数

```cpp
class Base {
public:
    ~Base() {  // 非虚析构函数
        std::cout << "Base destructor\n";
    }
};

class Derived : public Base {
public:
    ~Derived() {
        std::cout << "Derived destructor\n";
    }
};

// 问题：通过基类指针删除对象
Base* ptr = new Derived();
delete ptr;  // 只调用 Base 的析构函数，Derived 的析构函数不会被调用
```

### 6.2 解决方案

```cpp
class Base {
public:
    virtual ~Base() {  // 虚析构函数
        std::cout << "Base destructor\n";
    }
};

// 现在 delete ptr 会正确调用 Derived 的析构函数
```

## 7. 多继承与虚继承

### 7.1 多继承

```cpp
class A {
public:
    virtual void func() {}
};

class B {
public:
    virtual void func() {}
};

class C : public A, public B {
public:
    void func() override {  // 重写哪个？
        // 需要明确指定
    }
};
```

### 7.2 虚继承

```cpp
class Base {
public:
    int data;
};

class A : public virtual Base {};
class B : public virtual Base {};
class C : public A, public B {
    // C 只有一份 Base 的 data
};
```

## 8. 性能优化

### 8.1 避免不必要的虚函数

```cpp
// 如果不需要多态，不要使用虚函数
class Point {
    int x, y;
    // 不需要虚函数，Point 不会被继承
};
```

### 8.2 使用 final

```cpp
class Base {
public:
    virtual void func() {}
};

class Derived final : public Base {  // final 类
    void func() override {}
};

// 编译器可以优化 final 类的虚函数调用
```

## 9. 设计模式应用

### 9.1 策略模式

```cpp
class Strategy {
public:
    virtual void execute() = 0;
    virtual ~Strategy() = default;
};

class ConcreteStrategy1 : public Strategy {
    void execute() override {}
};

class Context {
    std::unique_ptr<Strategy> strategy;
public:
    void set_strategy(std::unique_ptr<Strategy> s) {
        strategy = std::move(s);
    }
    void do_something() {
        strategy->execute();  // 多态调用
    }
};
```

### 9.2 模板方法模式

```cpp
class Algorithm {
public:
    void run() {
        step1();
        step2();  // 虚函数，子类可以重写
        step3();
    }
protected:
    virtual void step2() = 0;
private:
    void step1() {}
    void step3() {}
};
```

## 10. 小结

多态和虚函数是 C++ 面向对象编程的核心，提供了灵活的运行时行为。

**核心要点**：
- 虚函数实现运行时多态
- 虚函数表存储函数地址
- 虚析构函数确保正确清理
- 纯虚函数定义接口
- 注意虚函数的性能开销

掌握多态和虚函数，可以设计出更灵活、更易扩展的 C++ 代码。
