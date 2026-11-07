# Jetpack Compose基础100题（含详细答案）

## 一、Compose核心概念（1-15题）

### 1. Jetpack Compose是什么？它与传统Android View系统的核心区别？
**答案**：Compose是Google推出的声明式UI工具包。核心区别：
- **传统View**：命令式，手动创建/更新View，XML+Kotlin混合
- **Compose**：声明式，描述UI状态，框架自动更新，纯Kotlin代码，无XML布局

### 2. Compose中的`@Composable`注解的作用？
**答案**：
- 标记函数为可组合函数
- 可在其中描述UI
- 被标记的函数只能在其他`@Composable`函数中调用
- 不能返回Unit以外的值

```kotlin
@Composable
fun Greeting(name: String) {
    Text(text = "Hello, $name!")
}
```

### 3. Compose的重组（Recomposition）是什么？触发条件？
**答案**：
- 当Composable读取的状态（State）变化时，框架自动重新调用该Composable生成新的UI
- Compose会智能跳过未受影响的Composable
- 触发条件：State值变化、传入参数变化、Key变化

### 4. Compose的重组为什么是"智能"的？
**答案**：
- Compose编译器在编译期插入代码，追踪哪些State被读取
- 只有读取了变化State的Composable才会重组
- 未读取的Composable会被跳过（Smart Recomposition）

### 5. Compose中的`remember`的作用？`remember` vs `rememberSaveable`？
**答案**：
| 特性 | remember | rememberSaveable |
|------|----------|------------------|
| 生命周期 | 重组时保持 | 重组+配置变更保持 |
| 存储位置 | 内存 | Bundle |
| 适用场景 | 临时计算结果 | 用户输入、UI状态 |
| 限制 | 进程死亡丢失 | 需可序列化 |

```kotlin
// remember - 配置变更后丢失
var count by remember { mutableIntStateOf(0) }

// rememberSaveable - 旋转屏幕后保持
var text by rememberSaveable { mutableStateOf("") }
```

### 6. `mutableStateOf`、`LiveData`、`Flow`在Compose中如何转换为State？
**答案**：
```kotlin
// mutableStateOf - 直接返回State
val state = mutableStateOf(0)

// LiveData
val liveData: LiveData<Int> = ...
val value by liveData.observeAsState(initial = 0)

// Flow
val flow: Flow<Int> = ...
val value by flow.collectAsState(initial = 0)

// Compose优先使用mutableStateOf
```

### 7. Compose中的`derivedStateOf`作用？
**答案**：
- 从其他State派生新State
- 只在依赖变化时重新计算
- 避免不必要的重组

```kotlin
val searchQuery by remember { mutableStateOf("") }
val items by remember { mutableStateOf(listOf<String>()) }

// 只在searchQuery或items变化时重新过滤
val filteredItems by remember {
    derivedStateOf {
        items.filter { it.contains(searchQuery, ignoreCase = true) }
    }
}
```

### 8. Compose中的`LaunchedEffect`、`DisposableEffect`、`SideEffect`的区别？
**答案**：
| 副作用API | 触发时机 | 清理 | 使用场景 |
|-----------|----------|------|----------|
| LaunchedEffect | Composable进入组合 | key变化时取消 | 启动协程 |
| DisposableEffect | Composable进入组合 | 离开组合或key变化 | 注册/注销监听器 |
| SideEffect | 每次成功重组 | 无 | 发布Compose状态到非Compose代码 |

```kotlin
// LaunchedEffect - 启动协程
LaunchedEffect(key1) {
    val data = api.fetchData()
    state.value = data
}

// DisposableEffect - 需要清理
DisposableEffect(lifecycleOwner) {
    val observer = LifecycleEventObserver { _, event ->
        // 处理生命周期事件
    }
    lifecycleOwner.lifecycle.addObserver(observer)
    onDispose {
        lifecycleOwner.lifecycle.removeObserver(observer)
    }
}

// SideEffect - 同步副作用
SideEffect {
    // 每次重组后执行
    analytics.trackScreen("Home")
}
```

### 9. `LaunchedEffect`的`key`参数作用？
**答案**：
- `key`变化时取消旧协程并启动新协程
- `LaunchedEffect(Unit)`：只在首次进入时执行
- `LaunchedEffect(key)`：在key变化时重新执行

```kotlin
// 只在首次进入时执行
LaunchedEffect(Unit) {
    viewModel.loadInitialData()
}

// 在userId变化时重新加载
LaunchedEffect(userId) {
    viewModel.loadUser(userId)
}
```

### 10. Compose中的`produceState`作用？
**答案**：
- 将非Compose状态（如网络请求）转换为Compose State
- 内部使用`LaunchedEffect`
- 自动管理协程生命周期

```kotlin
val user by produceState<User?>(initialValue = null, userId) {
    value = repository.getUser(userId)  // 在协程中执行
}
```

### 11. `snapshotFlow`的作用？
**答案**：
- 将Compose State转换为Kotlin Flow
- 当State变化时，Flow会发射新值
- 用于将Compose状态与非Compose的Flow API集成

```kotlin
val searchQuery by remember { mutableStateOf("") }

LaunchedEffect(Unit) {
    snapshotFlow { searchQuery.value }
        .debounce(300)
        .collect { query ->
            viewModel.search(query)
        }
}
```

### 12. Compose中的`CompositionLocal`是什么？
**答案**：
- 隐式传递数据的方式，类似传统View的Theme
- 通过`CompositionLocalProvider`提供值
- 子Composable通过`LocalXXX.current`获取

```kotlin
// 定义
val LocalElevation = compositionLocalOf { 0.dp }

// 提供
CompositionLocalProvider(LocalElevation provides 8.dp) {
    MyScreen()
}

// 消费
@Composable
fun MyScreen() {
    val elevation = LocalElevation.current
    Card(elevation = CardDefaults.cardElevation(elevation)) { }
}
```

### 13. `CompositionLocal`与参数传递的区别？何时使用？
**答案**：
| 特性 | 参数传递 | CompositionLocal |
|------|----------|------------------|
| 可见性 | 显式 | 隐式 |
| 追踪难度 | 易 | 难 |
| 适用场景 | 频繁变化的数据 | 深层传递且很少变化的数据 |
| 典型应用 | 业务数据 | 主题、字体、上下文、颜色 |

### 14. Compose中的`Modifier`是什么？链式调用的顺序为什么重要？
**答案**：
- Modifier用于装饰和增强Composable
- 链式调用顺序影响最终效果
- 每个Modifier会包装前一个

```kotlin
// 先padding再background：背景包含padding区域
Modifier.padding(16.dp).background(Color.Red)

// 先background再padding：padding在背景外
Modifier.background(Color.Red).padding(16.dp)
```

### 15. Compose编译器插件的作用？
**答案**：
- 在编译期插入代码
- 追踪State读取
- 标记可跳过重组的Composable
- 优化性能
- Compose的许多魔法都依赖编译器插件实现

---

## 二、Compose状态管理（16-30题）

### 16. Compose中状态提升（State Hoisting）的原则？
**答案**：
- 状态应提升到使用它的最低公共祖先
- 状态所有者负责存储和修改状态
- 子Composable通过参数接收状态和回调

```kotlin
// 状态提升前
@Composable
fun Counter() {
    var count by remember { mutableIntStateOf(0) }
    Column {
        Text("Count: $count")
        Button(onClick = { count++ }) { Text("Increment") }
    }
}

// 状态提升后
@Composable
fun Counter(count: Int, onIncrement: () -> Unit) {
    Column {
        Text("Count: $count")
        Button(onClick = onIncrement) { Text("Increment") }
    }
}

// 父级持有状态
@Composable
fun Parent() {
    var count by remember { mutableIntStateOf(0) }
    Counter(count = count, onIncrement = { count++ })
}
```

### 17. Compose中的单向数据流（UDF）模式？
**答案**：
- **状态向下流动**（State flows down）
- **事件向上传递**（Events flow up）
- UI是状态的函数：`UI = f(State)`

### 18. `ViewModel`在Compose中的使用方式？
**答案**：
```kotlin
@Composable
fun HomeScreen(
    viewModel: HomeViewModel = viewModel()  // 依赖LocalViewModelStoreOwner
) {
    val uiState by viewModel.uiState.collectAsState()
    // ...
}

// ViewModel存活于配置变更
class HomeViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()
}
```

### 19. `remember`与`ViewModel`存储状态的区别？
**答案**：
| 特性 | remember | ViewModel |
|------|----------|-----------|
| 生命周期 | Composable组合 | 配置变更 |
| 适用场景 | 临时UI状态 | 业务逻辑、跨屏幕数据 |
| 进程死亡 | 丢失 | 配合SavedStateHandle可恢复 |
| 作用域 | 局部 | 可跨Composable共享 |

### 20. Compose中如何处理配置变更（如旋转屏幕）？
**答案**：
- 使用`rememberSaveable`保存简单状态
- 使用`ViewModel`保存复杂状态
- 使用`SavedStateHandle`在ViewModel中保存状态

### 21. `collectAsState()`与`collectAsStateWithLifecycle()`的区别？
**答案**：
```kotlin
// 始终收集Flow
collectAsState()

// 生命周期感知，后台时暂停收集（避免后台更新UI）
collectAsStateWithLifecycle()

// 使用
val uiState by viewModel.uiState.collectAsStateWithLifecycle()
```

### 22. Compose中的`derivedStateOf` vs `remember` + 计算的区别？
**答案**：
```kotlin
// remember - 每次重组时重新计算（key不变时缓存）
val filtered by remember(searchQuery, items) {
    items.filter { it.contains(searchQuery) }
}

// derivedStateOf - 只在结果变化时触发重组
val filtered by remember {
    derivedStateOf {
        items.filter { it.contains(searchQuery) }
    }
}
```

### 23. Compose中如何优化列表滚动性能？`LazyColumn`的`key`参数？
**答案**：
```kotlin
LazyColumn {
    items(
        items = messages,
        key = { it.id }  // 提供唯一key
    ) { message ->
        MessageCard(message)
    }
}
```
- `key`帮助框架识别item
- 实现高效的插入/删除/移动动画
- 避免不必要的重组

### 24. `LazyListState`的作用？如何实现滚动到指定位置？
**答案**：
```kotlin
val listState = rememberLazyListState()

LazyColumn(state = listState) {
    items(100) { index ->
        Text("Item $index")
    }
}

// 滚动到指定位置
LaunchedEffect(Unit) {
    listState.scrollToItem(index = 50)      // 直接跳转
    listState.animateScrollToItem(index = 50)  // 带动画
}

// 监听滚动状态
val isScrolling by remember {
    derivedStateOf { listState.isScrollInProgress }
}
```

### 25. Compose中的`Paging`集成？`collectAsLazyPagingItems()`？
**答案**：
```kotlin
@Composable
fun MessageList(viewModel: MessageViewModel) {
    val lazyPagingItems = viewModel.messages.collectAsLazyPagingItems()

    LazyColumn {
        items(
            count = lazyPagingItems.itemCount,
            key = lazyPagingItems.itemKey { it.id }
        ) { index ->
            val message = lazyPagingItems[index]
            if (message != null) {
                MessageCard(message)
            }
        }

        // 加载状态
        lazyPagingItems.apply {
            when {
                loadState.refresh is LoadState.Loading -> {
                    item { CircularProgressIndicator() }
                }
                loadState.append is LoadState.Loading -> {
                    item { CircularProgressIndicator() }
                }
            }
        }
    }
}
```

### 26. Compose中`Flow`的`collectAsState`的`initial`参数作用？
**答案**：
- Flow开始收集前的初始值
- Flow是异步的，Composable首次组合时可能还没有值
- `initial`提供默认值避免空状态

### 27. Compose中如何处理`TextField`的状态？
**答案**：
```kotlin
// 传统方式
var text by remember { mutableStateOf("") }
TextField(
    value = text,
    onValueChange = { text = it }
)

// Compose 1.7+ TextFieldState
val textFieldState = rememberTextFieldState()
TextField(state = textFieldState)
```

### 28. `TextFieldState`（Compose 1.7+）相比传统`mutableStateOf`的优势？
**答案**：
- 内置文本编辑状态管理（光标位置、选择范围）
- 支持更复杂的文本操作
- 与`BasicTextField2`配合使用

### 29. Compose中如何实现表单验证？
**答案**：
```kotlin
@Composable
fun LoginForm(viewModel: LoginViewModel) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    // 派生验证状态
    val isEmailValid by remember {
        derivedStateOf { email.contains("@") }
    }
    val isFormValid by remember {
        derivedStateOf { isEmailValid && password.length >= 6 }
    }

    Column {
        TextField(
            value = email,
            onValueChange = { email = it },
            isError = !isEmailValid
        )
        TextField(
            value = password,
            onValueChange = { password = it },
            isError = password.length < 6
        )
        Button(
            onClick = { viewModel.login(email, password) },
            enabled = isFormValid
        ) {
            Text("Login")
        }
    }
}
```

### 30. Compose中的`SnapshotState`是什么？
**答案**：
- Compose的状态系统基础
- `mutableStateOf`返回`MutableState`，是`SnapshotState`的实现
- 支持快照机制，实现并发安全的状态读写

---

## 三、Compose布局（31-45题）

### 31. Compose中的基本布局Composable有哪些？
**答案**：
- `Column`：垂直排列
- `Row`：水平排列
- `Box`：堆叠/绝对定位
- `LazyColumn`/`LazyRow`：懒加载列表
- `LazyVerticalGrid`：懒加载网格

### 32. Compose中`Column`和`Row`的`Arrangement`和`Alignment`？
**答案**：
```kotlin
Column(
    verticalArrangement = Arrangement.SpaceBetween,  // 主轴
    horizontalAlignment = Alignment.CenterHorizontally  // 交叉轴
) { }

Row(
    horizontalArrangement = Arrangement.SpaceEvenly,   // 主轴
    verticalAlignment = Alignment.CenterVertically     // 交叉轴
) { }
```

### 33. Compose中`Modifier.fillMaxSize()`、`Modifier.fillMaxWidth()`的作用？
**答案**：
- `fillMaxSize()`：填满宽高
- `fillMaxWidth()`：填满宽度
- `fillMaxHeight()`：填满高度
- 可传`fraction`参数指定比例

```kotlin
Modifier.fillMaxWidth(0.5f)  // 填满50%宽度
```

### 34. Compose中`Box`的`contentAlignment`参数？
**答案**：
```kotlin
Box(
    modifier = Modifier.fillMaxSize(),
    contentAlignment = Alignment.Center  // 子元素默认居中对齐
) {
    Text("Centered")
    // 子元素可通过Modifier.align()单独设置对齐
    Text("TopStart", modifier = Modifier.align(Alignment.TopStart))
}
```

### 35. Compose中`ConstraintLayout`的使用场景？
**答案**：
- 复杂布局需要相对定位时
- 避免嵌套Column/Row带来的性能问题

```kotlin
ConstraintLayout(modifier = Modifier.fillMaxSize()) {
    val (button, text) = createRefs()

    Button(
        onClick = { },
        modifier = Modifier.constrainAs(button) {
            top.linkTo(parent.top, margin = 16.dp)
            start.linkTo(parent.start, margin = 16.dp)
        }
    ) { Text("Button") }

    Text(
        "Text",
        modifier = Modifier.constrainAs(text) {
            top.linkTo(button.bottom, margin = 16.dp)
            centerHorizontallyTo(parent)
        }
    )
}
```

### 36. Compose中`Scaffold`的作用？
**答案**：
```kotlin
Scaffold(
    topBar = { TopAppBar(title = { Text("Title") }) },
    bottomBar = { BottomAppBar { } },
    floatingActionButton = {
        FloatingActionButton(onClick = { }) {
            Icon(Icons.Default.Add, contentDescription = "Add")
        }
    },
    snackbarHost = { SnackbarHost(snackbarHostState) },
    drawerContent = { Text("Drawer") }
) { paddingValues ->
    // 自动处理内容padding（避免被系统栏遮挡）
    Content(modifier = Modifier.padding(paddingValues))
}
```

### 37. Compose中`Surface`和`Card`的区别？
**答案**：
| 特性 | Surface | Card |
|------|---------|------|
| 定位 | 基础容器 | 预配置的Surface |
| 圆角 | 可配置 | 默认有圆角 |
| 阴影 | 可配置 | 默认有阴影 |
| 规范 | 通用 | Material Card规范 |

### 38. Compose中`Spacer`的作用？
**答案**：
```kotlin
// 固定空间
Spacer(modifier = Modifier.height(16.dp))

// 在Row/Column中占据剩余空间
Row {
    Text("Start")
    Spacer(modifier = Modifier.weight(1f))  // 占据所有剩余空间
    Text("End")
}
```

### 39. Compose中`Divider`和`HorizontalDivider`/`VerticalDivider`？
**答案**：
- `Divider`：旧API（水平分割线）
- Compose 1.6+推荐使用：
  - `HorizontalDivider()`
  - `VerticalDivider()`

### 40. Compose中`LazyColumn`的`contentPadding`和`item`/`items`的区别？
**答案**：
```kotlin
LazyColumn(
    contentPadding = PaddingValues(horizontal = 16.dp)  // 整个列表的内边距
) {
    item { Header() }           // 单个item
    items(data) { item ->       // 多个item
        ItemCard(item)
    }
    itemsIndexed(data) { index, item ->  // 带索引
        ItemCard(index, item)
    }
}
```

### 41. Compose中`LazyVerticalStaggeredGrid`的作用？
**答案**：实现瀑布流布局（Pinterest风格），item高度可不同，自动填充空隙。

```kotlin
LazyVerticalStaggeredGrid(
    columns = StaggeredGridCells.Fixed(2),
    modifier = Modifier.fillMaxSize(),
    contentPadding = PaddingValues(16.dp)
) {
    items(images) { image ->
        AsyncImage(
            model = image.url,
            contentDescription = null,
            modifier = Modifier.fillMaxWidth()
        )
    }
}
```

### 42. Compose中`Modifier.padding()`和`Modifier.offset()`的区别？
**答案**：
| 特性 | padding | offset |
|------|---------|--------|
| 影响尺寸 | 是 | 否 |
| 影响布局 | 是 | 否 |
| 作用 | 内容周围添加空间 | 移动位置 |
| 其他元素 | 会被推开 | 不会被推开 |

### 43. Compose中`Modifier.graphicsLayer`的作用？
**答案**：
```kotlin
Modifier.graphicsLayer {
    alpha = 0.5f
    rotationZ = 45f
    scaleX = 1.2f
    scaleY = 1.2f
    translationX = 100f
    shadowElevation = 8f
}
// 不触发重组，性能更好
```

### 44. Compose中`SubcomposeLayout`的作用？
**答案**：
- 高级布局API
- 允许在布局过程中动态组合子Composable
- 用于需要基于子元素测量结果决定自身布局的复杂场景

### 45. Compose中`Layout`Composable的作用？
**答案**：
- 自定义布局的基础API
- 接收多个子元素，手动测量和放置
- 比`SubcomposeLayout`轻量，但功能有限

---

## 四、Compose主题与样式（46-55题）

### 46. Compose中`MaterialTheme`的作用？
**答案**：
```kotlin
MaterialTheme(
    colorScheme = colorScheme,
    typography = Typography,
    shapes = Shapes
) {
    // 子Composable自动继承主题
    MyApp()
}

// 访问主题属性
MaterialTheme.colorScheme.primary
MaterialTheme.typography.bodyLarge
MaterialTheme.shapes.medium
```

### 47. Compose中动态颜色（Dynamic Color）是什么？Android 12+？
**答案**：
```kotlin
val colorScheme = when {
    Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
        if (darkTheme) dynamicDarkColorScheme(context)
        else dynamicLightColorScheme(context)
    }
    else -> if (darkTheme) DarkColorScheme else LightColorScheme
}
```

### 48. Compose中`ColorScheme`和`Typography`如何自定义？
**答案**：
```kotlin
private val LightColorScheme = lightColorScheme(
    primary = Purple40,
    secondary = PurpleGrey40,
    tertiary = Pink40
)

private val Typography = Typography(
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
        letterSpacing = 0.5.sp
    )
)
```

### 49. Compose中`darkColorScheme`和`lightColorScheme`的切换？
**答案**：
```kotlin
@Composable
fun MyApp(darkTheme: Boolean = isSystemInDarkTheme()) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    MaterialTheme(colorScheme = colorScheme) {
        Surface { /* ... */ }
    }
}
```

### 50. Compose中`LocalContentColor`和`LocalTextStyle`的作用？
**答案**：
```kotlin
// CompositionLocal，提供当前内容颜色和文本样式
CompositionLocalProvider(LocalContentColor provides Color.White) {
    Text("White text")  // 自动使用白色
}
```

### 51. Compose中`Text`的`style`参数？
**答案**：
```kotlin
Text(
    text = "Hello",
    style = MaterialTheme.typography.headlineMedium
)

// 预定义样式：displayLarge/headlineMedium/titleSmall/bodyLarge/labelSmall等
```

### 52. Compose中`Icon`和`Image`的区别？
**答案**：
| 特性 | Icon | Image |
|------|------|-------|
| 用途 | 矢量图标 | 位图 |
| tint | 自动应用主题颜色 | 不自动tint |
| 资源 | ImageVector | painterResource/ImageBitmap |

### 53. Compose中`contentScale`参数？
**答案**：
```kotlin
Image(
    painter = painterResource(R.drawable.photo),
    contentDescription = null,
    contentScale = ContentScale.Crop  // 裁剪填满
    // ContentScale.Fit - 完整显示
    // ContentScale.FillBounds - 拉伸填满
    // ContentScale.Inside - 在边界内完整显示
)
```

### 54. Compose中`Brush`渐变？
**答案**：
```kotlin
// 线性渐变
Modifier.background(
    Brush.linearGradient(
        colors = listOf(Color.Red, Color.Blue)
    )
)

// 径向渐变
Brush.radialGradient(colors = listOf(Color.Red, Color.Blue))

// 扫描渐变
Brush.sweepGradient(colors = listOf(Color.Red, Color.Blue))

// 文本渐变
Text(
    text = "Gradient",
    style = TextStyle(
        brush = Brush.linearGradient(listOf(Color.Red, Color.Blue))
    )
)
```

### 55. Compose中`Shapes`主题？
**答案**：
```kotlin
val Shapes = Shapes(
    small = RoundedCornerShape(4.dp),
    medium = RoundedCornerShape(8.dp),
    large = RoundedCornerShape(16.dp)
)

// 使用
Card(shape = MaterialTheme.shapes.medium) { }
```

---

## 五、Compose动画（56-70题）

### 56. Compose中动画API的分类？
**答案**：
| 级别 | API | 场景 |
|------|-----|------|
| 高级别 | AnimatedVisibility, AnimatedContent, animateContentSize | 简单场景 |
| 低级别 | animate*AsState, updateTransition, Animatable | 复杂场景 |

### 57. `AnimatedVisibility`的作用？
**答案**：
```kotlin
var visible by remember { mutableStateOf(true) }

AnimatedVisibility(
    visible = visible,
    enter = fadeIn() + slideInVertically(),
    exit = fadeOut() + slideOutVertically()
) {
    Text("Hello")
}
```

### 58. `AnimatedContent`的作用？
**答案**：
```kotlin
var state by remember { mutableStateOf("A") }

AnimatedContent(
    targetState = state,
    transitionSpec = {
        fadeIn() togetherWith fadeOut()
    }
) { targetState ->
    Text("State: $targetState")
}
```

### 59. `animateContentSize`的作用？
**答案**：
```kotlin
var expanded by remember { mutableStateOf(false) }

Column(
    modifier = Modifier.animateContentSize()
) {
    Text("Header")
    if (expanded) {
        Text("Expanded content")  // 尺寸变化时自动动画
    }
}
```

### 60. `animate*AsState`系列函数？
**答案**：
```kotlin
val alpha by animateFloatAsState(targetValue = if (enabled) 1f else 0.5f)
val color by animateColorAsState(targetValue = if (selected) Color.Blue else Color.Gray)
val size by animateDpAsState(targetValue = if (expanded) 200.dp else 100.dp)
```

### 61. `updateTransition`的作用？
**答案**：
```kotlin
var currentState by remember { mutableStateOf(BoxState.Collapsed) }
val transition = updateTransition(currentState, label = "box transition")

val size by transition.animateDp { state ->
    when (state) {
        BoxState.Collapsed -> 0.dp
        BoxState.Expanded -> 300.dp
    }
}
val color by transition.animateColor { state ->
    when (state) {
        BoxState.Collapsed -> Color.Gray
        BoxState.Expanded -> Color.Red
    }
}
```

### 62. `Animatable` vs `animate*AsState`？
**答案**：
| 特性 | Animatable | animate*AsState |
|------|------------|-----------------|
| API风格 | 命令式 | 声明式 |
| 控制 | 手动（animateTo, snapTo） | 自动响应目标值 |
| 适用场景 | 复杂交互、手势驱动 | 简单状态变化 |

### 63. `rememberInfiniteTransition`的作用？
**答案**：
```kotlin
val infiniteTransition = rememberInfiniteTransition(label = "infinite")
val scale by infiniteTransition.animateFloat(
    initialValue = 1f,
    targetValue = 1.5f,
    animationSpec = infiniteRepeatable(
        animation = tween(1000),
        repeatMode = RepeatMode.Reverse
    ),
    label = "scale"
)
```

### 64. Compose中手势动画？
**答案**：
```kotlin
// draggable - 单向拖动
Modifier.draggable(
    orientation = Orientation.Horizontal,
    state = rememberDraggableState { delta ->
        // 处理拖动
    }
)

// anchoredDraggable - 双向拖动，吸附锚点（Compose 1.6+）
val state = remember {
    AnchoredDraggableState(
        initialValue = AnchoredValue.Start,
        anchors = DraggableAnchors {
            AnchoredValue.Start at 0f
            AnchoredValue.End at 500f
        }
    )
}
```

### 65. Compose中`Crossfade`的作用？
**答案**：
```kotlin
var currentPage by remember { mutableStateOf("A") }

Crossfade(targetState = currentPage) { page ->
    when (page) {
        "A" -> PageA()
        "B" -> PageB()
    }
}
```

### 66. `AnimationSpec`？`tween`、`spring`、`keyframes`？
**答案**：
```kotlin
// tween - 补间动画
animationSpec = tween(durationMillis = 300, easing = FastOutSlowInEasing)

// spring - 物理弹簧
animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy)

// keyframes - 关键帧
animationSpec = keyframes {
    durationMillis = 900
    0.0f at 0 with LinearEasing
    0.2f at 300 with FastOutLinearInEasing
    0.4f at 600
    1.0f at 900
}
```

### 67. Compose中`Easing`是什么？
**答案**：
- `FastOutSlowInEasing`：Material标准
- `LinearEasing`：线性
- `EaseInOut`：缓入缓出
- `EaseOut`：缓出

### 68. Compose中`Modifier.animateEnterExit`？
**答案**：
```kotlin
LazyColumn {
    items(data, key = { it.id }) { item ->
        ItemCard(
            item,
            modifier = Modifier.animateEnterExit(
                enter = slideInVertically(),
                exit = slideOutVertically()
            )
        )
    }
}
```

### 69. Compose中`LookaheadLayout`（实验性）的作用？
**答案**：
- 提前计算目标布局
- 实现更流畅的布局动画
- 用于共享元素过渡等高级动画效果

### 70. Compose中`SharedTransitionLayout`和`sharedElement`？
**答案**：
```kotlin
SharedTransitionLayout {
    AnimatedContent(targetState = showDetails) { state ->
        if (state) {
            DetailsScreen(
                modifier = Modifier.sharedElement(
                    state = rememberSharedContentState(key = "image"),
                    animatedVisibilityScope = this@AnimatedContent
                )
            )
        } else {
            ListScreen(
                modifier = Modifier.sharedElement(
                    state = rememberSharedContentState(key = "image"),
                    animatedVisibilityScope = this@AnimatedContent
                )
            )
        }
    }
}
```

---

## 六、Compose导航（71-80题）

### 71. Compose Navigation的核心组件？
**答案**：
- `NavHost`：显示当前目的地
- `NavController`：管理导航操作
- `NavGraph`：导航图定义
- `composable()`：定义可组合目的地

### 72. Compose Navigation中如何传递参数？
**答案**：
```kotlin
NavHost(navController, startDestination = "home") {
    composable("home") { HomeScreen() }
    composable(
        "detail/{id}",
        arguments = listOf(navArgument("id") { type = NavType.IntType })
    ) { backStackEntry ->
        val id = backStackEntry.arguments?.getInt("id")
        DetailScreen(id)
    }
}

// 导航
navController.navigate("detail/123")
```

### 73. Compose Navigation中`rememberNavController()`的作用？
**答案**：
- 创建并记住NavController实例
- 在重组时保持同一实例
- 管理返回栈和当前目的地

### 74. Compose Navigation中深链接（Deep Link）配置？
**答案**：
```kotlin
composable(
    "detail/{id}",
    deepLinks = listOf(
        navDeepLink { uriPattern = "myapp://detail/{id}" }
    )
) { ... }

// AndroidManifest.xml
<intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="myapp" android:host="detail" />
</intent-filter>
```

### 75. Compose Navigation中`ViewModel`的作用域？
**答案**：
- 默认跟随`NavBackStackEntry`生命周期
- 离开导航目标时清除
- 可通过`viewModelStoreOwner`参数指定作用域

### 76. Compose Navigation中`navigation()`嵌套导航图？
**答案**：
```kotlin
NavHost(navController, startDestination = "home") {
    navigation(startDestination = "home/feed", route = "home") {
        composable("home/feed") { FeedScreen() }
        composable("home/profile") { ProfileScreen() }
    }
    navigation(startDestination = "search/results", route = "search") {
        composable("search/results") { SearchResults() }
    }
}
```

### 77. Compose Navigation中底部导航栏实现？
**答案**：
```kotlin
val navController = rememberNavController()
val currentBackStack by navController.currentBackStackEntryAsState()
val currentDestination = currentBackStack?.destination

Scaffold(
    bottomBar = {
        NavigationBar {
            items.forEach { item ->
                NavigationBarItem(
                    icon = { Icon(item.icon, null) },
                    label = { Text(item.label) },
                    selected = currentDestination?.hierarchy?.any { it.route == item.route } == true,
                    onClick = {
                        navController.navigate(item.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                )
            }
        }
    }
) { padding ->
    NavHost(navController, startDestination = "home") { }
}
```

### 78. Compose Navigation中`popUpTo`和`launchSingleTop`？
**答案**：
```kotlin
navController.navigate("home") {
    popUpTo("home") { inclusive = true }  // 弹出到home，包含home
    launchSingleTop = true  // 如果已在栈顶，不创建新实例
}
```

### 79. Compose Navigation中类型安全导航？
**答案**：
```kotlin
// Compose 1.7+ 使用Kotlin Serialization
@Serializable
object Home

@Serializable
data class Detail(val id: Int)

NavHost(navController, startDestination = Home) {
    composable<Home> { HomeScreen() }
    composable<Detail> { backStackEntry ->
        val detail: Detail = backStackEntry.toRoute()
        DetailScreen(detail.id)
    }
}

// 导航
navController.navigate(Detail(id = 123))
```

### 80. Compose Navigation与Hilt ViewModel集成？
**答案**：
```kotlin
@Composable
fun DetailScreen(
    viewModel: DetailViewModel = hiltViewModel()
) {
    // Hilt自动注入，生命周期绑定导航目标
}
```

---

## 七、Compose与View互操作（81-90题）

### 81. Compose中如何嵌入传统View（`AndroidView`）？
**答案**：
```kotlin
AndroidView(
    factory = { context ->
        // 首次创建View
        CustomView(context).apply {
            // 初始化
        }
    },
    update = { view ->
        // 每次重组时更新
        view.setData(data)
    },
    modifier = Modifier.fillMaxWidth()
)
```

### 82. `AndroidView`的`factory`和`update`参数区别？
**答案**：
| 参数 | 调用次数 | 用途 |
|------|----------|------|
| factory | 1次 | 首次创建View |
| update | 多次 | 每次重组时更新View状态 |

### 83. Compose中`ComposeView`的作用？
**答案**：
- 在传统View系统中嵌入Compose
- 继承自`AbstractComposeView`
- 在Activity/Fragment中作为容器使用`setContent { ... }`

```kotlin
// Activity中
val composeView = ComposeView(this)
composeView.setContent {
    MaterialTheme {
        MyComposable()
    }
}
setContentView(composeView)
```

### 84. Compose中如何处理传统View的点击事件和Compose手势冲突？
**答案**：
- 使用`Modifier.pointerInteropFilter`
- 调整嵌套顺序
- Compose手势系统优先于传统View的触摸事件分发

### 85. Compose中`DisposableEffect`清理`AndroidView`资源？
**答案**：
```kotlin
AndroidView(
    factory = { context -> CustomView(context) },
    modifier = Modifier.fillMaxWidth()
) { view ->
    view.setData(data)
    // 清理在onRelease中
}

// 或使用DisposableEffect
DisposableEffect(Unit) {
    val listener = object : SomeListener { }
    someObject.addListener(listener)
    onDispose {
        someObject.removeListener(listener)
    }
}
```

### 86. Compose中`rememberCoroutineScope()` vs `LaunchedEffect`？
**答案**：
| 特性 | rememberCoroutineScope | LaunchedEffect |
|------|------------------------|----------------|
| 返回值 | CoroutineScope | 无 |
| 启动方式 | 手动启动 | 自动启动 |
| 使用场景 | 事件回调中启动协程 | Composable进入组合时启动 |

```kotlin
val scope = rememberCoroutineScope()

Button(onClick = {
    scope.launch {
        // 在点击时启动协程
    }
}) { }
```

### 87. Compose中`SnapshotState`与传统`Observable`模式的区别？
**答案**：
- `SnapshotState`：细粒度、自动追踪依赖
- 传统`Observable`：需要手动注册/注销观察者
- Compose编译器自动处理依赖追踪

### 88. Compose中`ViewCompositionStrategy`的作用？
**答案**：
```kotlin
composeView.setViewCompositionStrategy(
    ViewCompositionStrategy.DisposeOnLifecycleDestroyed(lifecycle)
)

// 选项：
// DisposeOnDetachedFromWindow（默认）
// DisposeOnLifecycleDestroyed
// DisposeOnViewTreeLifecycleDestroyed
```

### 89. Compose中如何在Fragment中使用？
**答案**：
```kotlin
class MyFragment : Fragment() {
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View = ComposeView(requireContext()).apply {
        setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnViewTreeLifecycleDestroyed)
        setContent {
            MaterialTheme {
                MyComposable()
            }
        }
    }
}
```

### 90. Compose中`setViewCompositionStrategy`的作用？
**答案**：
- 配置ComposeView的Composition策略
- 决定何时dispose Composition
- 重要避免内存泄漏
- 特别是在RecyclerView等复用场景中

---

## 八、Compose性能优化与测试（91-100题）

### 91. Compose中`@Stable`和`@Immutable`注解的作用？
**答案**：
| 注解 | 含义 | 适用场景 |
|------|------|----------|
| @Immutable | 类完全不可变 | 数据类（所有val） |
| @Stable | 类稳定，属性变化会通知 | 有mutableState的类 |

```kotlin
@Immutable
data class User(val name: String, val age: Int)

@Stable
class UserRepository {
    var users by mutableStateOf(listOf<User>())
}
```

### 92. Compose中如何避免不必要的重组？
**答案**：
1. 使用`@Stable`/`@Immutable`标记数据类
2. 使用`remember`缓存计算结果
3. 使用`derivedStateOf`派生状态
4. 将状态提升到合适层级
5. 使用`key()`控制重组范围

### 93. Compose中`key()` Composable的作用？
**答案**：
```kotlin
LazyColumn {
    items(data, key = { it.id }) { item ->
        // 提供唯一标识，帮助框架正确识别元素
        ListItem(item)
    }
}
```

### 94. Compose中`Modifier.then()`的作用？
**答案**：
```kotlin
// 连接两个Modifier
val baseModifier = Modifier.padding(16.dp)
val finalModifier = baseModifier.then(Modifier.background(Color.Red))

// 用于条件性添加Modifier
fun Modifier.conditional(condition: Boolean, modifier: Modifier.() -> Modifier) =
    if (condition) then(modifier(Modifier)) else this
```

### 95. Compose中`@Preview`注解的作用？参数？
**答案**：
```kotlin
@Preview(
    showBackground = true,
    backgroundColor = 0xFFFFFFFF,
    uiMode = UI_MODE_NIGHT_YES,
    device = Devices.PIXEL_4,
    fontScale = 1.5f,
    locale = "zh-rCN"
)
@Composable
fun PreviewGreeting() {
    Greeting("Android")
}
```

### 96. Compose中如何编写单元测试？
**答案**：
```kotlin
class MyComposeTest {
    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun greeting_displaysCorrectText() {
        composeTestRule.setContent {
            Greeting("Compose")
        }

        composeTestRule
            .onNodeWithText("Hello, Compose!")
            .assertExists()
    }

    @Test
    fun button_click_triggersAction() {
        var clicked = false
        composeTestRule.setContent {
            Button(onClick = { clicked = true }) {
                Text("Click me")
            }
        }

        composeTestRule.onNodeWithText("Click me").performClick()
        assertTrue(clicked)
    }
}
```

### 97. Compose中语义（Semantics）测试？
**答案**：
```kotlin
// 添加语义
Modifier.semantics {
    contentDescription = "User avatar"
    role = Role.Image
}

// 测试中使用
composeTestRule
    .onNodeWithContentDescription("User avatar")
    .assertExists()

composeTestRule
    .onNodeWithRole(Role.Button)
    .performClick()
```

### 98. Compose中`performTouchInput`和手势测试？
**答案**：
```kotlin
composeTestRule.onNodeWithTag("slider")
    .performTouchInput {
        down(center)
        moveBy(Offset(100f, 0f))
        up()
    }

// 或简写
.performTouchInput { swipeRight() }
```

### 99. Compose中布局 Inspector和Recomposition计数器？
**答案**：
- Android Studio的Layout Inspector支持Compose
- 开启"Show Recomposition Counts"查看每个Composable的重组次数
- 帮助定位性能问题

### 100. Compose中`Baseline Profiles`对启动性能的提升？
**答案**：
- 通过预编译关键路径代码（如Compose运行时）
- 减少JIT编译开销
- 提升应用启动和运行时性能
- 使用`BaselineProfileGenerator`生成

```kotlin
@RunWith(AndroidJUnit4::class)
class BaselineProfileGenerator {
    @get:Rule val rule = MacrobenchmarkRule()

    @Test
    fun generate() {
        rule.collectBaselineProfile("com.example.app") {
            // 执行关键用户场景
            startActivityAndWait()
            // ...
        }
    }
}
```

---

> **总结**：Jetpack Compose是Android现代UI开发的未来方向，掌握声明式UI思维、状态管理、重组原理和性能优化是成为Compose专家的核心。建议结合官方文档、Codelab和实际项目经验来巩固这些知识。
