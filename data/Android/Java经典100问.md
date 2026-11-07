# Java语言100题（含详细答案）

## 一、Java基础语法（1-15题）

### 1. Java中`==`和`equals()`的区别是什么？
**答案**：`==`比较引用地址（基本类型比较值），`equals()`比较对象内容。`String`重写了`equals()`比较字符序列，但`==`仍比较引用。
```java
String s1 = new String("hello");
String s2 = new String("hello");
System.out.println(s1 == s2);      // false（不同对象）
System.out.println(s1.equals(s2)); // true（内容相同）

String s3 = "hello";
String s4 = "hello";
System.out.println(s3 == s4);      // true（字符串常量池）
```

### 2. `String`、`StringBuilder`、`StringBuffer`的区别？
**答案**：
| 特性 | String | StringBuilder | StringBuffer |
|------|--------|---------------|--------------|
| 可变性 | 不可变 | 可变 | 可变 |
| 线程安全 | 安全（不可变） | 不安全 | 安全（synchronized） |
| 性能 | 低（频繁创建对象） | 高 | 较高（有同步开销） |
| 使用场景 | 字符串常量 | 单线程字符串操作 | 多线程字符串操作 |

### 3. `final`、`finally`、`finalize`的区别？
**答案**：
- `final`：修饰类（不可继承）、方法（不可重写）、变量（不可变）
- `finally`：try-catch的必执行块，用于释放资源
- `finalize()`：Object的方法，GC前调用（已废弃@Deprecated since 9）

### 4. `hashCode()`和`equals()`的契约关系？为什么重写`equals()`必须重写`hashCode()`？
**答案**：
- 契约：相等对象必须有相同hashCode；hashCode相同对象不一定相等（哈希碰撞）
- 原因：`HashMap`先用hashCode定位桶，再用equals比较。不一致会导致对象无法正确查找
```java
// 违反契约的反面教材
class Person {
    String name;
    @Override
    public boolean equals(Object obj) { /* 比较name */ }
    // 未重写hashCode()！
}
Map<Person, String> map = new HashMap<>();
map.put(new Person("Tom"), "value");
map.get(new Person("Tom")); // null！因为hashCode不同
```

### 5. Java中`&`和`&&`、`|`和`||`的区别？
**答案**：
- `&`和`|`：逻辑运算符（也会按位运算），两边都执行
- `&&`和`||`：短路运算符，左边能确定结果时右边不执行
```java
int a = 0;
if (false && (a++ > 0)) {} // a仍为0，右边不执行
if (false & (a++ > 0)) {}  // a变为1，两边都执行
```

### 6. `break`、`continue`、`return`的区别？`break`在循环和switch中的行为？
**答案**：
- `break`：跳出当前循环/switch
- `continue`：跳过本次循环，进入下一次
- `return`：结束方法，返回结果

带标签的`break`可跳出外层循环：
```java
outer: for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
        if (j == 1) break outer; // 跳出外层循环
    }
}
```

### 7. Java中的值传递还是引用传递？
**答案**：Java只有值传递。对象参数传递的是引用的副本。
```java
void modify(StringBuilder sb) {
    sb.append(" world");      // 对外可见（修改对象内容）
    sb = new StringBuilder("new"); // 对外不可见（修改引用副本）
}
```

### 8. `switch`语句支持哪些数据类型？Java 12+有什么新特性？
**答案**：
- 支持：`byte`/`short`/`int`/`char`、包装类、`String`（Java 7+）、`enum`
- Java 12+新特性：
```java
// switch表达式（返回值）
int result = switch (day) {
    case MONDAY, FRIDAY, SUNDAY -> 6;  // 箭头语法，多case合并
    case TUESDAY                -> 7;
    case THURSDAY, SATURDAY     -> 8;
    case WEDNESDAY              -> 9;
    default -> throw new IllegalStateException();
};

// yield返回值（代码块）
int result = switch (day) {
    case MONDAY -> {
        System.out.println("Monday");
        yield 1;
    }
    default -> 0;
};
```

### 9. `instanceof`运算符的作用？Java 16+的模式匹配特性？
**答案**：判断对象是否是指定类型或其子类。
```java
// Java 16+ 模式匹配
if (obj instanceof String s) { // 直接声明变量s
    System.out.println(s.length()); // 无需强转
}

// switch模式匹配（Java 17+预览，21正式）
String formatted = switch (obj) {
    case Integer i -> String.format("int %d", i);
    case String s  -> String.format("String %s", s);
    default        -> "unknown";
};
```

### 10. Java中的自动装箱和拆箱原理？可能带来的问题？
**答案**：
- 原理：编译器自动插入`Integer.valueOf()`和`intValue()`
- `Integer.valueOf()`缓存-128~127，超出范围创建新对象
```java
Integer a = 100, b = 100;
Integer c = 200, d = 200;
System.out.println(a == b); // true（缓存内）
System.out.println(c == d); // false（缓存外，不同对象）

// NullPointerException风险
Integer num = null;
int n = num; // 拆箱时NPE！
```

### 11. `try-with-resources`语法的作用和使用条件？
**答案**：自动关闭实现了`AutoCloseable`接口的资源。
```java
try (BufferedReader br = new BufferedReader(new FileReader("file.txt"));
     PrintWriter pw = new PrintWriter(new FileWriter("out.txt"))) {
    // 使用资源
} // 自动按声明逆序关闭，即使发生异常

// 支持在try前声明（Java 9+）
BufferedReader br = new BufferedReader(new FileReader("file.txt"));
try (br) {
    // 使用
}
```

### 12. Java中的泛型擦除（Type Erasure）是什么？带来的限制？
**答案**：编译时泛型信息被擦除，替换为边界类型。
```java
List<String> list = new ArrayList<>();
// 编译后：List list = new ArrayList();

// 限制：
List<String>[] array = new List<String>[10]; // 编译错误！不能创建泛型数组
if (list instanceof List<String>) {} // 编译错误！运行时无法获取泛型类型
```

### 13. `<? extends T>`和`<? super T>`的区别？PECS原则？
**答案**：
- `<? extends T>`：上界通配符，可读不可写（Producer）
- `<? super T>`：下界通配符，可写不可读（Consumer）
- PECS = Producer-Extends, Consumer-Super
```java
// Producer：从集合中读取T及其子类
void readFrom(List<? extends Number> list) {
    Number n = list.get(0); // 可以读
    // list.add(1); // 编译错误！不能写
}

// Consumer：向集合中写入T及其子类
void writeTo(List<? super Integer> list) {
    list.add(1); // 可以写
    // Integer i = list.get(0); // 编译错误！只能读Object
}
```

### 14. Java中的注解（Annotation）是什么？元注解有哪些？
**答案**：元数据标记。
- `@Retention`：保留策略（SOURCE/CLASS/RUNTIME）
- `@Target`：作用目标（METHOD/FIELD/TYPE等）
- `@Documented`：包含在Javadoc中
- `@Inherited`：子类继承
- `@Repeatable`（Java 8）：可重复注解

### 15. `@FunctionalInterface`注解的作用？
**答案**：标记函数式接口（只有一个抽象方法），编译器会检查。
```java
@FunctionalInterface
interface MyFunction {
    void apply(); // 唯一抽象方法
    default void defaultMethod() {} // 可以有默认方法
    static void staticMethod() {}    // 可以有静态方法
}
```

---

## 二、面向对象（16-30题）

### 16. 接口（Interface）和抽象类（Abstract Class）的区别？Java 8+的变化？
**答案**：
| 特性 | 接口 | 抽象类 |
|------|------|--------|
| 继承/实现 | 多实现 | 单继承 |
| 构造器 | 无 | 有 |
| 成员变量 | 默认public static final | 任意 |
| 方法实现 | Java 8+支持default/static | 支持 |
| 访问修饰符 | 默认public | 任意 |

Java 8+接口支持`default`方法和`static`方法；Java 9+支持`private`方法。

### 17. 多态（Polymorphism）的实现方式？运行时多态和编译时多态？
**答案**：
- **编译时多态**（静态绑定）：方法重载（Overload），编译器根据参数类型决定
- **运行时多态**（动态绑定）：方法重写（Override），JVM根据实际对象类型调用方法（vtable机制）

### 18. 方法重载（Overload）和方法重写（Override）的区别？
**答案**：
| 特性 | 重载 | 重写 |
|------|------|------|
| 位置 | 同类或子类 | 子类对父类 |
| 方法名 | 相同 | 相同 |
| 参数 | 不同（类型/数量/顺序） | 相同 |
| 返回类型 | 可不同 | 相同或协变返回 |
| 访问修饰符 | 可不同 | 不能更严格 |
| 异常 | 可不同 | 不能更宽泛 |
| 绑定 | 编译时 | 运行时 |

### 19. `super`和`this`关键字的用法？
**答案**：
- `this`：指向当前对象，调用当前类构造器/方法/属性
- `super`：指向父类，调用父类构造器/方法
- 构造器中`this()`和`super()`必须在第一行且互斥

### 20. 构造器（Constructor）的特点？能否被继承？能否被重写？
**答案**：
- 方法名与类名相同，无返回值，不可继承，不可重写
- 子类构造器默认调用父类无参构造器（需显式`super()`）
- 父类没有无参构造器时，子类必须显式调用父类有参构造器

### 21. 静态代码块、构造代码块、构造方法的执行顺序？
**答案**：
1. 父类静态代码块
2. 子类静态代码块
3. 父类构造代码块
4. 父类构造方法
5. 子类构造代码块
6. 子类构造方法

### 22. Java中为什么不允许静态方法访问非静态成员？
**答案**：静态方法属于类，在类加载时存在；非静态成员属于对象实例，需要对象创建后才存在。静态方法调用时可能对象还未创建。

### 23. `Object`类中有哪些方法？各自作用？
**答案**：
- `equals()`/`hashCode()`/`toString()`：对象比较、哈希、字符串表示
- `clone()`：对象拷贝
- `finalize()`：GC前调用（已废弃）
- `getClass()`：获取运行时类
- `notify()`/`notifyAll()`/`wait()`：线程通信

### 24. `clone()`方法的浅拷贝和深拷贝？如何实现深拷贝？
**答案**：
```java
// 浅拷贝：引用类型共享
class Person implements Cloneable {
    String name;
    Address address; // 引用类型
    @Override
    public Person clone() throws CloneNotSupportedException {
        return (Person) super.clone(); // 浅拷贝
    }
}

// 深拷贝实现方式1：递归clone
@Override
public Person clone() throws CloneNotSupportedException {
    Person clone = (Person) super.clone();
    clone.address = this.address.clone(); // 递归拷贝引用对象
    return clone;
}

// 深拷贝实现方式2：序列化
public Person deepClone() {
    try (ByteArrayOutputStream baos = new ByteArrayOutputStream();
         ObjectOutputStream oos = new ObjectOutputStream(baos)) {
        oos.writeObject(this);
        try (ObjectInputStream ois = new ObjectInputStream(
                new ByteArrayInputStream(baos.toByteArray()))) {
            return (Person) ois.readObject();
        }
    }
}
```

### 25. 内部类（Inner Class）有哪些类型？各自特点？
**答案**：
1. **成员内部类**：依赖外部类实例，`Outer.this`访问外部类
2. **静态内部类**：不依赖实例，类似顶级类，可独立存在
3. **局部内部类**：方法内定义，只能访问final或effectively final变量
4. **匿名内部类**：无类名，常用于回调。Lambda可替代单方法匿名内部类

### 26. 为什么局部内部类和匿名内部类只能访问final或effectively final的局部变量？
**答案**：内部类对象生命周期可能长于局部变量。Java通过复制变量值实现，若变量可变会导致数据不一致，因此限制为final。

### 27. Java中的继承和组合如何选择？
**答案**：优先组合。
- "is-a"关系用继承：Dog is Animal
- "has-a"关系用组合：Car has Engine
- 组合更灵活，低耦合，避免继承层次过深

### 28. 什么是里氏替换原则（LSP）？在Java中如何遵循？
**答案**：子类必须能够替换父类而不影响程序正确性。
- 遵循方式：不重写父类非抽象方法改变行为、子类前置条件不强于父类、后置条件不弱于父类
- 反面教材：正方形继承长方形，修改了setWidth/setHeight逻辑

### 29. `default`方法在接口中的引入解决了什么问题？可能带来的问题？
**答案**：
- 解决接口演化问题：向现有接口添加方法而不破坏实现类
- 问题：多接口default方法冲突
```java
interface A { default void method() { System.out.println("A"); } }
interface B { default void method() { System.out.println("B"); } }
class C implements A, B {
    @Override
    public void method() {
        A.super.method(); // 显式指定
    }
}
```

### 30. Java中的密封类（Sealed Class，Java 17+）是什么？作用？
**答案**：限制继承层次，只有`permits`指定的类可以继承。
```java
public sealed class Shape permits Circle, Rectangle, Square { }
public final class Circle extends Shape { }
public non-sealed class Rectangle extends Shape { } // 允许进一步继承
public sealed class Square extends Shape permits SpecialSquare { }
```

---

## 三、集合框架（31-45题）

### 31. Java集合框架的顶层接口有哪些？Collection和Map的关系？
**答案**：
- Collection（List、Set、Queue）和Map是两大顶层接口，无继承关系
- List：有序可重复；Set：无序不重复；Queue：先进先出；Map：键值对

### 32. `ArrayList`和`LinkedList`的区别？使用场景？
**答案**：
| 特性 | ArrayList | LinkedList |
|------|-----------|------------|
| 底层 | 动态数组 | 双向链表 |
| 随机访问 | O(1) | O(n) |
| 尾部插入 | O(1)均摊 | O(1) |
| 中间插入/删除 | O(n) | O(1)（需先查找） |
| 内存 | 连续，有预留空间 | 分散，额外指针开销 |
| 场景 | 查询多 | 频繁增删 |

### 33. `ArrayList`的扩容机制？
**答案**：
- 默认初始容量10
- 扩容时`grow()`计算新容量为旧容量的1.5倍：`oldCapacity + (oldCapacity >> 1)`
- 复制元素到新数组：`Arrays.copyOf(elementData, newCapacity)`
- 可通过`ensureCapacity()`预分配减少扩容次数

### 34. `HashMap`的数据结构？JDK 1.8的优化？
**答案**：
- 数据结构：数组 + 链表 + 红黑树
- 1.8优化：
  - 链表长度≥8且数组长度≥64时转红黑树（查询O(log n)）
  - 扩容时链表拆分（高低位），避免重新计算hash
  - 头插法改尾插法，避免并发扩容死循环

### 35. `HashMap`的`put`方法流程？
**答案**：
1. 计算hash：`(h = key.hashCode()) ^ (h >>> 16)`（高位参与运算，减少碰撞）
2. 计算索引：`(n - 1) & hash`
3. 无冲突：直接插入
4. 冲突：链表/红黑树处理（key相同则覆盖，不同则追加）
5. 检查扩容：`size > threshold`（capacity * loadFactor）

### 36. `HashMap`为什么容量是2的幂次？
**答案**：`(n-1) & hash`等价于`hash % n`，位运算效率更高。2的幂次保证散列均匀，减少碰撞。

### 37. `HashMap`线程不安全的表现？`ConcurrentHashMap`如何保证线程安全？
**答案**：
- `HashMap`多线程下可能死循环（1.7头插法）、数据丢失
- `ConcurrentHashMap`：
  - 1.7：分段锁（Segment，默认16段）
  - 1.8：CAS + synchronized（锁单个桶），读操作无锁（volatile保证可见性）

### 38. `Hashtable`和`HashMap`的区别？`Collections.synchronizedMap`的问题？
**答案**：
| 特性 | Hashtable | HashMap |
|------|-----------|---------|
| 线程安全 | 是（全表synchronized） | 否 |
| null键值 | 不允许 | 允许一个null键，多个null值 |
| 出现时间 | JDK 1.0 | JDK 1.2 |
| 迭代器 | fail-fast | fail-fast |

`Collections.synchronizedMap`锁粒度大（锁整个Map），性能差，推荐使用`ConcurrentHashMap`。

### 39. `TreeMap`和`HashMap`的区别？底层数据结构？
**答案**：
- `TreeMap`：基于红黑树，按键排序（自然排序或Comparator），操作O(log n)
- `HashMap`：基于哈希表，无序，操作平均O(1)

### 40. `LinkedHashMap`如何保证插入顺序或访问顺序？
**答案**：维护双向链表。
```java
// accessOrder=false（默认）：按插入顺序
// accessOrder=true：按访问顺序（LRU缓存实现基础）
Map<String, String> lruCache = new LinkedHashMap<String, String>(16, 0.75f, true) {
    @Override
    protected boolean removeEldestEntry(Map.Entry<String, String> eldest) {
        return size() > 100; // 超过100条移除最老的
    }
};
```

### 41. 如何实现一个线程安全的LRU缓存？
**答案**：
```java
class LRUCache<K, V> extends LinkedHashMap<K, V> {
    private final int capacity;
    public LRUCache(int capacity) {
        super(capacity, 0.75f, true);
        this.capacity = capacity;
    }
    @Override
    protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
        return size() > capacity;
    }
}
// 线程安全版本
Map<K, V> syncLru = Collections.synchronizedMap(new LRUCache<>(100));
// 或 ConcurrentHashMap + ConcurrentLinkedDeque 实现
```

### 42. `CopyOnWriteArrayList`的原理？适用场景？
**答案**：
- 原理：写操作（add/set）时复制新数组，读操作无锁
- 适用：读多写少场景
- 缺点：写操作开销大，数据最终一致性，迭代器弱一致性（基于创建时的快照）

### 43. `PriorityQueue`的底层实现？是否线程安全？
**答案**：
- 基于小顶堆（数组实现）
- 非线程安全
- 线程安全版本：`PriorityBlockingQueue`

### 44. `HashSet`、`LinkedHashSet`、`TreeSet`的底层分别是什么？
**答案**：
- `HashSet` -> `HashMap`（值为常量`Object PRESENT = new Object()`）
- `LinkedHashSet` -> `LinkedHashMap`
- `TreeSet` -> `TreeMap`（实现`NavigableSet`）

### 45. `fail-fast`和`fail-safe`迭代器的区别？
**答案**：
- `fail-fast`（ArrayList、HashMap）：检测到并发修改抛`ConcurrentModificationException`（modCount检查）
- `fail-safe`（CopyOnWriteArrayList、ConcurrentHashMap）：迭代时复制集合，不抛异常

---

## 四、异常处理（46-50题）

### 46. Java异常体系的顶层结构？Checked Exception和Unchecked Exception的区别？
**答案**：
```
Throwable
├── Error（不可恢复，如OutOfMemoryError、StackOverflowError）
└── Exception
    ├── RuntimeException（Unchecked，如NPE、ArrayIndexOutOfBoundsException）
    └── 其他Exception（Checked，如IOException、SQLException）
```
- Checked：编译时检查，必须处理（try-catch或throws）
- Unchecked：运行时异常，不强制处理

### 47. `try-catch-finally`中，`finally`块一定会执行吗？什么情况下不执行？
**答案**：
- 几乎一定执行
- 不执行情况：`System.exit()`、JVM崩溃、`try`前有`return`（未进入try）、线程被中断/杀死

### 48. `try-with-resources`相比传统`try-finally`关闭资源的优势？
**答案**：
- 代码更简洁
- 异常处理更优雅（suppressed异常保留）
- 自动按声明逆序关闭
- 避免资源泄漏

### 49. 如何正确自定义异常？
**答案**：
```java
public class BusinessException extends RuntimeException {
    private final int code;

    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
    }

    public BusinessException(String message, Throwable cause) {
        super(message, cause);
        this.code = 500;
    }

    // getter
}
```

### 50. `throw`和`throws`的区别？
**答案**：
- `throw`：在方法体内抛出异常对象
- `throws`：在方法签名声明可能抛出的异常类型，调用者需处理

---

## 五、IO与NIO（51-60题）

### 51. Java IO的分类？字节流和字符流的区别？
**答案**：
- 按方向：输入流/输出流
- 按类型：
  - 字节流（`InputStream`/`OutputStream`）：处理二进制数据
  - 字符流（`Reader`/`Writer`）：处理文本数据，自动编解码

### 52. 装饰器模式在Java IO中的体现？
**答案**：
```java
InputStream is = new FileInputStream("file.txt");
BufferedInputStream bis = new BufferedInputStream(is); // 添加缓冲
DataInputStream dis = new DataInputStream(bis);         // 添加数据类型支持
```

### 53. `Serializable`接口的作用？`serialVersionUID`的作用？
**答案**：
- `Serializable`：标记类可序列化
- `serialVersionUID`：版本控制，反序列化时检查一致性，不一致抛`InvalidClassException`
- 建议显式声明，避免自动生成的UID因类结构变化而改变

### 54. `transient`关键字的作用？
**答案**：修饰的字段不会被序列化。
```java
public class User implements Serializable {
    private String username;
    private transient String password; // 不序列化
    private transient int age;       // 不序列化，反序列化后为默认值0
}
```

### 55. NIO（New IO）的核心组件？
**答案**：
- `Channel`：双向通道，连接数据源
- `Buffer`：数据容器
- `Selector`：多路复用，单线程管理多个Channel

### 56. `Buffer`的`flip()`、`clear()`、`rewind()`方法的区别？
**答案**：
| 方法 | position | limit | 作用 |
|------|----------|-------|------|
| flip() | 0 | =原position | 准备读（写模式->读模式） |
| clear() | 0 | =capacity | 准备写（读模式->写模式，数据不清除） |
| rewind() | 0 | 不变 | 重读 |

### 57. NIO中的`DirectByteBuffer`和`HeapByteBuffer`的区别？
**答案**：
| 特性 | HeapByteBuffer | DirectByteBuffer |
|------|---------------|------------------|
| 位置 | JVM堆 | 堆外内存（native） |
| 创建/回收 | 快（GC管理） | 慢（malloc/free） |
| IO性能 | 差（需拷贝到内核） | 好（零拷贝） |
| 适用场景 | 小数据量 | 大文件/网络IO |

### 58. NIO.2（Java 7+）的主要改进？
**答案**：
- `Path`替代`File`
- `Paths`工厂方法
- `Files`工具类：`copy()`、`move()`、`walkFileTree()`、`readAllLines()`
- `WatchService`文件监控
- `AsynchronousFileChannel`异步IO

### 59. `FileChannel`的`transferTo`/`transferFrom`方法的优势？
**答案**：零拷贝（Zero-Copy），文件数据直接从内核空间传输到网络/文件，无需经过用户空间。

### 60. Java中的异步IO（AIO）和NIO的区别？
**答案**：
- NIO：同步非阻塞，多路复用，线程轮询检查
- AIO：异步非阻塞，操作完成后回调通知

---

## 六、并发编程（61-80题）

### 61. 进程、线程、协程的区别？
**答案**：
| 特性 | 进程 | 线程 | 协程 |
|------|------|------|------|
| 资源 | 独立地址空间 | 共享进程资源 | 用户态，极小栈 |
| 调度 | OS | OS | 程序/运行时 |
| 切换开销 | 大（MB级） | 中（KB级） | 极小（几十字节） |
| 通信 | IPC复杂 | 共享内存，需同步 | 直接共享 |
| Java支持 | ProcessBuilder | Thread | 虚拟线程（Java 21+） |

### 62. 线程的几种状态？状态转换图？
**答案**：
```
NEW -> RUNNABLE -> [BLOCKED/WAITING/TIMED_WAITING] -> TERMINATED
```
- NEW：新建
- RUNNABLE：可运行/运行中
- BLOCKED：阻塞，等待锁
- WAITING：无限等待（wait/join）
- TIMED_WAITING：限时等待（sleep/wait(timeout)）
- TERMINATED：终止

### 63. `Thread`类的`start()`和`run()`方法的区别？
**答案**：
- `start()`：启动新线程，JVM调用`run()`
- `run()`：普通方法调用，不会启动新线程

### 64. `sleep()`和`wait()`的区别？
**答案**：
| 特性 | sleep() | wait() |
|------|---------|--------|
| 所属类 | Thread | Object |
| 锁释放 | 不释放 | 释放 |
| 唤醒方式 | 时间到自动唤醒 | notify()/notifyAll()或超时 |
| 使用场景 | 暂停执行 | 线程通信 |

### 65. `notify()`和`notifyAll()`的区别？
**答案**：
- `notify()`：随机唤醒一个等待线程
- `notifyAll()`：唤醒所有等待线程
- 建议使用`notifyAll()`避免信号丢失

### 66. `synchronized`关键字的作用？底层实现原理？
**答案**：
- 作用：保证原子性、可见性、有序性
- 底层：JVM层面`monitorenter`/`monitorexit`字节码
- 对象头Mark Word存储锁状态：无锁 -> 偏向锁 -> 轻量级锁 -> 重量级锁

### 67. Java锁的升级过程？
**答案**：
1. **无锁**：对象刚创建
2. **偏向锁**：无竞争时，CAS替换Thread ID，同一线程再次进入无需同步
3. **轻量级锁**：有竞争，CAS自旋获取锁
4. **重量级锁**：自旋失败，线程阻塞，操作系统Mutex

### 68. `volatile`关键字的作用？能保证原子性吗？
**答案**：
- 保证可见性（MESI缓存一致性协议）
- 禁止指令重排序
- **不能保证原子性**：`i++`仍需`synchronized`或`AtomicInteger`

### 69. `synchronized`和`ReentrantLock`的区别？
**答案**：
| 特性 | synchronized | ReentrantLock |
|------|-------------|---------------|
| 实现 | JVM关键字 | API（AQS） |
| 锁释放 | 自动（异常也释放） | 手动unlock() |
| 可中断 | 否 | 是（lockInterruptibly） |
| 超时获取 | 否 | 是（tryLock(timeout)） |
| 公平锁 | 否 | 支持 |
| 条件变量 | 一个（wait/notify） | 多个（Condition） |
| 性能 | JDK 6+优化后接近 | 略优 |

### 70. `ReentrantLock`的公平锁和非公平锁的区别？
**答案**：
- **公平锁**：按请求顺序获取锁（FIFO），吞吐量低但避免饥饿
- **非公平锁**：允许插队（默认），吞吐量大，可能饥饿

### 71. `ReadWriteLock`/`StampedLock`的作用？
**答案**：
```java
// ReadWriteLock：读读共享，读写互斥，写写互斥
ReadWriteLock rwLock = new ReentrantReadWriteLock();
Lock readLock = rwLock.readLock();
Lock writeLock = rwLock.writeLock();

// StampedLock（Java 8）：支持乐观读
StampedLock lock = new StampedLock();
long stamp = lock.tryOptimisticRead(); // 乐观读，不加锁
if (!lock.validate(stamp)) { // 验证，若被写则升级为读锁
    stamp = lock.readLock();
}
```

### 72. `CountDownLatch`、`CyclicBarrier`、`Semaphore`的区别？
**答案**：
| 特性 | CountDownLatch | CyclicBarrier | Semaphore |
|------|---------------|---------------|-----------|
| 作用 | 等待多个线程完成 | 线程互相等待 | 控制并发数 |
| 可重用 | 否（一次性） | 是（可reset） | 是 |
| 典型场景 | 主线程等待子线程 | 分阶段计算 | 限流 |

### 73. `CompletableFuture`的作用？常用方法？
**答案**：
```java
CompletableFuture.supplyAsync(() -> fetchData())
    .thenApply(data -> process(data))      // 转换结果
    .thenCompose(result -> save(result))    // 扁平化（返回Future）
    .thenCombine(otherFuture, (a, b) -> merge(a, b)) // 合并两个Future
    .exceptionally(ex -> fallbackValue)     // 异常处理
    .whenComplete((result, ex) -> log());   // 完成回调
```

### 74. `ThreadLocal`的原理和使用场景？内存泄漏问题？
**答案**：
- 原理：每个线程有独立副本，通过`ThreadLocalMap`（Thread内部变量）实现
- 场景：数据库连接、用户上下文、SimpleDateFormat线程安全
- 内存泄漏：`ThreadLocalMap`的Entry是`WeakReference<ThreadLocal>`，但Value是强引用。线程池场景下线程复用，Value无法回收。
- 解决：使用完调用`threadLocal.remove()`

### 75. Java中的线程池（ThreadPoolExecutor）核心参数？
**答案**：
- `corePoolSize`：核心线程数
- `maximumPoolSize`：最大线程数
- `keepAliveTime`：空闲线程存活时间
- `workQueue`：任务队列
- `threadFactory`：线程工厂
- `handler`：拒绝策略

### 76. 线程池的拒绝策略有哪些？
**答案**：
- `AbortPolicy`：抛异常（默认）
- `CallerRunsPolicy`：调用者线程执行
- `DiscardPolicy`：静默丢弃
- `DiscardOldestPolicy`：丢弃最老任务

### 77. `Executors`工厂方法的隐患？为什么阿里巴巴手册不推荐？
**答案**：
- `FixedThreadPool`和`SingleThreadPool`：使用无界队列`LinkedBlockingQueue`，可能OOM
- `CachedThreadPool`：允许无限线程（`Integer.MAX_VALUE`），可能资源耗尽
- `ScheduledThreadPool`：使用`DelayedWorkQueue`，同样可能OOM
- **推荐**：手动创建`ThreadPoolExecutor`，明确队列大小和拒绝策略

### 78. `ForkJoinPool`的原理？`Work-Stealing`算法？
**答案**：
- 分治任务并行执行
- 每个线程有双端队列（Deque）
- 自己从队尾取任务，空闲时从其他线程队头"偷"任务
- 减少线程竞争，提升CPU利用率

### 79. `synchronized`在JDK 1.6后的优化？
**答案**：
- **偏向锁**：无竞争时CAS替换Thread ID
- **轻量级锁**：有竞争时CAS自旋
- **锁粗化**：相邻同步块合并
- **锁消除**：逃逸分析确定对象不会被其他线程访问，去掉同步
- **自适应自旋**：根据历史成功率调整自旋次数

### 80. Java内存模型（JMM）中的`happens-before`规则？
**答案**：
1. 程序顺序规则：同一线程中前面的操作happens-before后面的
2. 锁规则：unlock happens-before后面对同一个锁的lock
3. volatile规则：写happens-before后面对该变量的读
4. 线程启动：Thread.start() happens-before线程中的操作
5. 线程终止：线程中的操作happens-before线程终止检测
6. 中断规则：interrupt() happens-before检测到中断
7. 传递性：A happens-before B，B happens-before C，则A happens-before C

---

## 七、JVM（81-90题）

### 81. JVM的内存结构（运行时数据区）？
**答案**：
```
线程共享：
├── 堆（Heap）：对象实例、数组
└── 元空间（Metaspace，Java 8+）：类元数据、常量池
    （Java 7-：永久代PermGen）

线程私有：
├── 程序计数器：当前线程执行的字节码行号
├── 虚拟机栈：栈帧（局部变量、操作数栈、动态链接、方法返回）
└── 本地方法栈：Native方法

直接内存（Direct Memory）：NIO使用，不受JVM堆大小限制
```

### 82. 堆内存的分代模型？各区域的作用？
**答案**：
- **新生代**（1/3）：对象诞生和短期存活
  - Eden（8/10）：新对象分配
  - Survivor0（1/10）、Survivor1（1/10）：Minor GC后存活对象复制
- **老年代**（2/3）：长期存活对象（默认15次GC后晋升）
- 默认比例新生代:老年代 = 1:2，Eden:S0:S1 = 8:1:1

### 83. 对象的创建过程？
**答案**：
1. 类加载检查：常量池能否定位到类符号引用，类是否已加载
2. 分配内存：指针碰撞（Serial、ParNew，内存规整）或空闲列表（CMS，内存不规整）
3. 初始化零值：保证对象字段无需赋值即可使用
4. 设置对象头：Mark Word、类型指针、数组长度
5. 执行`<init>`构造器

### 84. 对象在堆中的内存布局？
**答案**：
```
对象头（Header）
├── Mark Word（64位JVM：64bit）
│   ├── 哈希码
│   ├── GC分代年龄
│   ├── 锁状态标志
│   └── 偏向线程ID/epoch
├── 类型指针（Klass Pointer）：指向类元数据
└── 数组长度（仅数组对象）

实例数据（Instance Data）：字段值

对齐填充（Padding）：8字节对齐
```

### 85. 垃圾回收的判断标准？引用计数法和可达性分析？
**答案**：
- **引用计数法**：每个对象维护引用计数，为0时回收。缺点：循环引用问题
- **可达性分析**（Java使用）：从GC Roots出发，不可达则回收
  - GC Roots：栈引用、静态变量、常量、JNI引用、CLDB（类加载器）

### 86. Java中的四种引用类型？
**答案**：
| 引用类型 | 回收时机 | 典型应用 |
|----------|----------|----------|
| 强引用 | 不回收 | 普通对象 |
| 软引用（SoftReference） | 内存不足时 | 缓存 |
| 弱引用（WeakReference） | 下次GC时 | WeakHashMap、ThreadLocal |
| 虚引用（PhantomReference） | 随时，需配合ReferenceQueue | 跟踪对象回收、堆外内存释放 |

### 87. 常见的垃圾回收器？各自特点和适用场景？
**答案**：
| 回收器 | 算法 | 特点 | 场景 |
|--------|------|------|------|
| Serial | 复制/标记-整理 | 单线程，简单高效 | 客户端模式 |
| ParNew | 复制 | Serial多线程版 | 配合CMS |
| Parallel Scavenge | 复制 | 吞吐量优先 | 后台计算 |
| CMS | 标记-清除 | 低停顿，并发回收 | Web应用（已废弃） |
| G1 | 标记-整理+复制 | 分区回收，可预测停顿 | 大堆，平衡吞吐和延迟（默认） |
| ZGC | 染色指针 | 低延迟（<10ms），TB级堆 | 低延迟应用（Java 11+） |
| Shenandoah |  Brooks指针 | 低延迟 | 低延迟应用（Java 12+） |

### 88. CMS垃圾回收器的执行过程？缺点？
**答案**：
- 过程：初始标记（STW）-> 并发标记 -> 重新标记（STW）-> 并发清除
- 缺点：
  - CPU敏感（并发阶段占用CPU）
  - 浮动垃圾（并发阶段产生的新垃圾）
  - 内存碎片（标记-清除算法）
  - Concurrent Mode Failure（并发期间老年代空间不足，退化为Serial Old）

### 89. G1垃圾回收器的特点？Region概念？
**答案**：
- 将堆划分为多个Region（1~32MB，2的幂次）
- Region角色不固定：Eden、Survivor、Old、Humongous（大对象）
- 优先回收价值最大的Region（回收时间×回收空间）
- 可预测停顿时间：`-XX:MaxGCPauseMillis`
- 整体标记-整理，局部复制算法

### 90. 类加载的过程？
**答案**：
1. **加载**：读取二进制流，生成Class对象
2. **验证**：文件格式、元数据、字节码、符号引用验证
3. **准备**：静态变量赋零值（`static int a = 123;` 此时a=0）
4. **解析**：符号引用转直接引用
5. **初始化**：执行`<clinit>()`（静态变量赋值、静态代码块）

---

## 八、Java新特性与高级话题（91-100题）

### 91. Java 8的Lambda表达式和函数式接口？
**答案**：
```java
// Lambda表达式
List<String> list = Arrays.asList("a", "b", "c");
list.forEach(s -> System.out.println(s));
list.forEach(System.out::println); // 方法引用

// 四大函数式接口
Predicate<String> predicate = s -> s.length() > 3; // 断言
Function<String, Integer> function = String::length; // 转换
Consumer<String> consumer = System.out::println;     // 消费
Supplier<String> supplier = () -> "hello";           // 供给
```

### 92. Stream API的核心操作？中间操作和终端操作？
**答案**：
```java
List<Integer> result = list.stream()
    .filter(n -> n > 0)      // 中间操作：过滤
    .map(n -> n * 2)         // 中间操作：映射
    .sorted()                // 中间操作：排序
    .distinct()              // 中间操作：去重
    .limit(10)               // 中间操作：限制
    .collect(Collectors.toList()); // 终端操作：收集

// 其他终端操作
.anyMatch(n -> n > 100);    // 是否匹配
.reduce(0, Integer::sum);   // 归约
.count();                   // 计数
.forEach(System.out::println); // 遍历
```

### 93. Optional类的作用？正确使用方式？
**答案**：
```java
// 正确用法
String result = Optional.ofNullable(getName())
    .map(String::toUpperCase)
    .filter(s -> s.length() > 3)
    .orElse("DEFAULT");

// 错误用法（违背设计意图）
Optional<String> opt = Optional.ofNullable(getName());
if (opt.isPresent()) {  // 不要这样用！
    return opt.get();
}
```

### 94. Java 9+的模块化系统（JPMS）？
**答案**：
```java
// module-info.java
module com.example.app {
    requires java.base;        // 依赖模块
    requires transitive java.sql; // 传递依赖
    exports com.example.api;   // 导出包（外部可访问）
    opens com.example.internal; // 开放包（反射访问）
    provides com.example.Service 
        with com.example.ServiceImpl; // SPI提供服务
    uses com.example.Service;   // SPI消费服务
}
```

### 95. Java 10的局部变量类型推断（`var`）？使用限制？
**答案**：
```java
var list = new ArrayList<String>(); // 编译器推断为ArrayList<String>
var stream = list.stream();         // 推断为Stream<String>

// 限制：
// var a;          // 错误！必须初始化
// var b = null;   // 错误！无法推断类型
// public var c = 1; // 错误！不能用于成员变量/参数/返回类型
```

### 96. Java 14+的`record`关键字？作用？
**答案**：
```java
// 编译器自动生成：构造器、getter、equals、hashCode、toString
public record Person(String name, int age) { }

// 使用
Person p = new Person("Tom", 20);
System.out.println(p.name()); // Tom
System.out.println(p.age());  // 20

// 可添加方法、静态字段、紧凑构造器
public record Person(String name, int age) {
    public Person {
        if (age < 0) throw new IllegalArgumentException();
    }
}
```

### 97. Java 21的虚拟线程（Virtual Threads，Project Loom）？
**答案**：
```java
// 创建虚拟线程
Thread.startVirtualThread(() -> {
    System.out.println("Running in virtual thread: " + Thread.currentThread());
});

// 使用ExecutorService
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    IntStream.range(0, 1_000_000).forEach(i -> {
        executor.submit(() -> {
            Thread.sleep(Duration.ofSeconds(1));
            return i;
        });
    });
} // 可轻松创建数百万虚拟线程，适合高并发IO密集型应用
```

### 98. Java中的SPI机制（Service Provider Interface）？
**答案**：
```java
// 1. 定义接口（核心库）
public interface Logger { void log(String msg); }

// 2. 实现类（第三方jar）
public class FileLogger implements Logger { }

// 3. 在META-INF/services/com.example.Logger文件中写入：
// com.example.FileLogger

// 4. 加载
ServiceLoader<Logger> loader = ServiceLoader.load(Logger.class);
for (Logger logger : loader) {
    logger.log("hello");
}
```

### 99. 反射（Reflection）的原理？优缺点？
**答案**：
- **原理**：JVM在方法区存储类的元数据，反射通过`Class`对象访问
- **优点**：灵活、框架基础（Spring、Hibernate）
- **缺点**：
  - 性能低（绕过JIT优化，需安全检查）
  - 破坏封装（可访问private成员）
  - 编译时无法检查，运行时可能异常

### 100. Java中的注解处理器（Annotation Processor）？编译时代码生成？
**答案**：
```java
@SupportedAnnotationTypes("com.example.AutoGenerate")
@SupportedSourceVersion(SourceVersion.RELEASE_21)
public class MyProcessor extends AbstractProcessor {
    @Override
    public boolean process(Set<? extends TypeElement> annotations, RoundEnvironment roundEnv) {
        for (Element element : roundEnv.getElementsAnnotatedWith(AutoGenerate.class)) {
            // 生成代码
            generateCode(element);
        }
        return true;
    }
}
// 典型应用：Lombok、Dagger、Room、MapStruct
```

---

> **总结**：Java语言博大精深，从基础语法到JVM底层，从集合框架到并发编程，每个知识点都值得深入理解。建议结合源码阅读和实际项目经验来巩固这些知识。
