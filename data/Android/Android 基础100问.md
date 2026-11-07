# Android基础100题（含详细答案）

## 一、Activity与生命周期（1-20题）

### 1. Android四大组件是什么？各自作用？
**答案**：
- **Activity**：用户界面交互，一个Activity通常对应一个屏幕
- **Service**：后台运行，无界面，长期执行任务
- **BroadcastReceiver**：接收系统或应用广播，响应全局事件
- **ContentProvider**：跨应用数据共享，封装数据暴露URI接口

### 2. Activity的7个生命周期回调方法？调用顺序？
**答案**：
```
onCreate() → onStart() → onResume() → onPause() → onStop() → onDestroy()
```
- `onRestart()`：从停止到重新开始时调用（在onStart之前）

完整生命周期：
```
创建：onCreate → onStart → onResume
前台：onResume（用户可交互）
部分可见：onPause（如弹窗覆盖）
不可见：onStop → onRestart → onStart → onResume
销毁：onPause → onStop → onDestroy
```

### 3. Activity A启动Activity B，两者的生命周期调用顺序？
**答案**：
```
A.onPause() → B.onCreate() → B.onStart() → B.onResume() → A.onStop()
```
- 如果B是透明或对话框样式，A不会调用onStop()
- 从B返回A：
```
B.onPause() → A.onRestart() → A.onStart() → A.onResume() → B.onStop() → B.onDestroy()
```

### 4. onSaveInstanceState()和onRestoreInstanceState()的作用？何时调用？
**答案**：
- **onSaveInstanceState()**：在Activity可能被系统销毁前保存临时状态
  - 调用时机：onStop()之前（通常在onPause之后）
  - 触发条件：旋转屏幕、内存不足被回收、系统配置变更
  - 存储数据到Bundle

- **onRestoreInstanceState()**：重建时恢复状态
  - 调用时机：onStart()之后，onResume()之前
  - 也可在onCreate(Bundle savedInstanceState)中恢复

```kotlin
override fun onSaveInstanceState(outState: Bundle) {
    super.onSaveInstanceState(outState)
    outState.putString("edit_text", editText.text.toString())
    outState.putInt("scroll_position", scrollY)
}

override fun onRestoreInstanceState(savedInstanceState: Bundle) {
    super.onRestoreInstanceState(savedInstanceState)
    val text = savedInstanceState.getString("edit_text")
    val position = savedInstanceState.getInt("scroll_position")
}
```

### 5. Activity的启动模式（LaunchMode）有哪些？
**答案**：
| 启动模式 | 特点 | 适用场景 |
|----------|------|----------|
| **standard** | 每次启动创建新实例，放入启动者所在栈 | 默认模式 |
| **singleTop** | 栈顶复用，调用onNewIntent() | 通知跳转、搜索 |
| **singleTask** | 栈内复用，清空其上Activity，调用onNewIntent() | 主页面、WebView |
| **singleInstance** | 独占新任务栈，不允许其他Activity进入 | 来电界面、闹钟 |

### 6. singleTask和singleInstance的区别？
**答案**：
| 特性 | singleTask | singleInstance |
|------|------------|----------------|
| 任务栈 | 与其他Activity共享 | 独占一个任务栈 |
| 其他Activity | 可共存于同一栈 | 不允许进入 |
| 返回行为 | 返回时先退当前栈 | 直接返回调用者 |
| 典型应用 | 主页面 | 来电、闹钟 |

### 7. TaskAffinity是什么？
**答案**：
- Activity所属的任务栈名称
- 默认是应用包名
- 可通过`android:taskAffinity`属性指定
- 用于控制Activity进入哪个任务栈
- 配合`allowTaskReparenting`可实现任务迁移

```xml
<activity android:name=".SecondActivity"
    android:taskAffinity="com.example.newtask" />
```

### 8. Activity的FLAG有哪些常用值？
**答案**：
```kotlin
// FLAG_ACTIVITY_NEW_TASK - 新建任务栈（类似singleInstance）
val intent = Intent(this, SecondActivity::class.java)
intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

// FLAG_ACTIVITY_CLEAR_TOP - 清除目标Activity上方的所有Activity
intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)

// FLAG_ACTIVITY_SINGLE_TOP - 栈顶复用（类似singleTop）
intent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)

// FLAG_ACTIVITY_NO_HISTORY - 不保留在历史栈中
intent.addFlags(Intent.FLAG_ACTIVITY_NO_HISTORY)

// FLAG_ACTIVITY_CLEAR_TASK - 清除整个任务栈
intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK)

// FLAG_ACTIVITY_REORDER_TO_FRONT - 将已有Activity移到栈顶
intent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
```

### 9. onNewIntent()何时调用？
**答案**：
- 当Activity启动模式为singleTop、singleTask、singleInstance
- 且实例已存在时
- 通过onNewIntent()传递新Intent，而非创建新实例

```kotlin
override fun onNewIntent(intent: Intent?) {
    super.onNewIntent(intent)
    setIntent(intent)  // 更新Intent
    // 处理新Intent数据
    handleIntent(intent)
}
```

### 10. Activity之间如何传递数据？
**答案**：
```kotlin
// 1. Intent putExtra（基本类型）
val intent = Intent(this, SecondActivity::class.java)
intent.putExtra("name", "Tom")
intent.putExtra("age", 25)
startActivity(intent)

// 2. 传递Parcelable对象
intent.putExtra("user", User("Tom", 25))

// 3. 传递Bundle
val bundle = Bundle().apply {
    putString("key", "value")
}
intent.putExtras(bundle)

// 4. Activity Result API（替代startActivityForResult）
val launcher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
    if (result.resultCode == RESULT_OK) {
        val data = result.data?.getStringExtra("result")
    }
}
launcher.launch(intent)

// 5. 共享ViewModel（同父Fragment或Activity）
```

### 11. Activity Result API替代了startActivityForResult？如何使用？
**答案**：
```kotlin
class MainActivity : AppCompatActivity() {

    // 注册ActivityResultLauncher
    private val pickImageLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        // 处理返回结果
        uri?.let { imageView.setImageURI(it) }
    }

    private val takePictureLauncher = registerForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { success: Boolean ->
        if (success) {
            // 拍照成功
        }
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            // 权限已授予
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 启动
        pickImageLauncher.launch("image/*")
        permissionLauncher.launch(Manifest.permission.CAMERA)
    }
}
```

### 12. Activity的windowSoftInputMode属性？
**答案**：
```xml
<activity
    android:windowSoftInputMode="adjustResize|stateHidden" />
```
| 值 | 作用 |
|----|------|
| adjustResize | 调整布局大小，内容上移 |
| adjustPan | 平移内容，不调整布局 |
| adjustNothing | 不做任何调整 |
| stateHidden | 进入页面时隐藏键盘 |
| stateAlwaysVisible | 进入页面时显示键盘 |
| stateUnchanged | 保持上一个状态 |

### 13. 什么是透明Activity？如何配置？
**答案**：
```xml
<style name="TransparentActivity">
    <item name="android:windowBackground">@android:color/transparent</item>
    <item name="android:windowIsTranslucent">true</item>
    <item name="android:windowAnimationStyle">@null</item>
</style>

<activity android:theme="@style/TransparentActivity" />
```
- 注意：透明Activity不会调用onStop()，而是onPause()
- 因为底层Activity仍然可见

### 14. Activity的configChanges属性？
**答案**：
```xml
<activity
    android:configChanges="orientation|screenSize|keyboardHidden|locale" />
```
- 声明哪些配置变化由Activity自己处理（不重建）
- 配置变化时调用onConfigurationChanged()而非重建

```kotlin
override fun onConfigurationChanged(newConfig: Configuration) {
    super.onConfigurationChanged(newConfig)
    if (newConfig.orientation == Configuration.ORIENTATION_LANDSCAPE) {
        // 横屏处理
    }
}
```

### 15. 如何处理屏幕旋转不重建Activity？
**答案**：
```xml
<!-- 方法1：声明自己处理配置变化 -->
<activity android:configChanges="orientation|screenSize" />

<!-- 方法2：使用ViewModel保存状态（推荐） -->
```

```kotlin
// 使用ViewModel
class MyViewModel : ViewModel() {
    var data: String = ""
}

class MainActivity : AppCompatActivity() {
    private val viewModel: MyViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 旋转后viewModel数据仍在
        textView.text = viewModel.data
    }
}
```

### 16. Activity的theme中windowIsFloating作用？
**答案**：
- 使Activity显示为对话框样式（浮动窗口）
- 背景Activity仍然可见
- 尺寸由windowBackground或layout决定

```xml
<style name="DialogActivity">
    <item name="android:windowIsFloating">true</item>
    <item name="android:windowBackground">@drawable/dialog_background</item>
</style>
```

### 17. 什么是Task和Back Stack？
**答案**：
- **Task**：用户执行特定任务时交互的Activity集合
- **Back Stack**：以栈形式管理Activity，按返回键弹出栈顶
- 一个应用可有多个Task
- 最近任务列表显示的是Task

### 18. Activity的process属性？
**答案**：
```xml
<activity android:process=":remote" />
```
- 指定Activity运行的进程名
- 默认在主进程（包名）
- `:remote`表示私有进程（包名:remote）
- 用于隔离内存或处理特定任务（如WebView、音乐播放）

### 19. 什么是Activity的exported属性？
**答案**：
```xml
<activity android:exported="false" />
```
- 是否允许外部应用启动该Activity
- `true`：可被外部启动（包含intent-filter时默认true）
- `false`：仅限本应用（Android 12+强制要求显式声明）
- 安全建议：非必要不exported，防止被恶意调用

### 20. Android 12+的SplashScreen API？
**答案**：
```xml
<!-- themes.xml -->
<style name="Theme.MyApp" parent="Theme.Material3.DayNight.NoActionBar">
    <item name="android:windowSplashScreenBackground">@color/splash_background</item>
    <item name="android:windowSplashScreenAnimatedIcon">@drawable/splash_icon</item>
    <item name="android:windowSplashScreenAnimationDuration">300</item>
</style>
```
- 系统级启动画面API
- 替代第三方启动屏库
- 自动适配深色模式

---

## 二、Fragment（21-35题）

### 21. Fragment的生命周期与Activity的关系？
**答案**：
```
Fragment生命周期嵌套在Activity中：

onAttach → onCreate → onCreateView → onViewCreated → onActivityCreated → onStart → onResume → onPause → onStop → onDestroyView → onDestroy → onDetach

与Activity对应关系：
- Activity.onCreate → Fragment.onAttach/onCreate/onCreateView/onActivityCreated
- Activity.onStart → Fragment.onStart
- Activity.onResume → Fragment.onResume
- Activity.onPause → Fragment.onPause
- Activity.onStop → Fragment.onStop
- Activity.onDestroy → Fragment.onDestroyView/onDestroy/onDetach
```

### 22. Fragment的add和replace区别？
**答案**：
| 操作 | 效果 | 生命周期 | 适用场景 |
|------|------|----------|----------|
| add | 添加到容器，可多个共存 | onAttach→onCreate→onCreateView→onResume | Tab切换、多层叠加 |
| replace | 先remove所有再add | 旧Fragment: onPause→onStop→onDestroyView；新Fragment: 完整创建 | 页面切换 |

### 23. Fragment的show/hide和attach/detach区别？
**答案**：
| 操作 | 视图状态 | 生命周期 | 使用场景 |
|------|----------|----------|----------|
| show/hide | 可见性变化，不销毁视图 | onHiddenChanged() | 快速切换，保留状态 |
| attach/detach | 销毁/重建视图 | onDestroyView/onCreateView | 内存优化，释放视图 |

```kotlin
// show/hide
fragmentTransaction.show(fragment)
fragmentTransaction.hide(fragment)

// attach/detach
fragmentTransaction.detach(fragment)  // 保留实例，销毁视图
fragmentTransaction.attach(fragment)  // 重建视图
```

### 24. FragmentTransaction的commit和commitNow区别？
**答案**：
| 方法 | 执行时机 | 是否允许状态丢失 | 使用限制 |
|------|----------|------------------|----------|
| commit() | 异步，加入主线程队列 | 默认不允许 | 必须在状态保存前调用 |
| commitNow() | 立即同步执行 | 不允许 | 不能加入回退栈 |
| commitAllowingStateLoss() | 异步，允许状态丢失 | 允许 | 不推荐 |

### 25. Fragment的setRetainInstance(true)作用？（已废弃）
**答案**：
- 配置变更时保留Fragment实例（不重建）
- 已废弃（Android 28+）
- **推荐使用ViewModel替代**

```kotlin
// 旧方式（已废弃）
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    retainInstance = true
}

// 新方式
class MyViewModel : ViewModel() {
    // 配置变更自动保留
}
```

### 26. Fragment间如何通信？
**答案**：
```kotlin
// 方法1：通过Activity中转（接口回调）
interface OnFragmentInteractionListener {
    fun onFragmentInteraction(data: String)
}

// 方法2：共享ViewModel（推荐）
class SharedViewModel : ViewModel() {
    val selected = MutableLiveData<String>()
}

// Fragment A
viewModel.selected.value = "item"

// Fragment B
viewModel.selected.observe(viewLifecycleOwner) { item ->
    // 更新UI
}

// 方法3：Fragment Result API
// Fragment A发送
setFragmentResult("requestKey", bundleOf("bundleKey" to "result"))

// Fragment B接收
parentFragmentManager.setFragmentResultListener("requestKey", this) { _, bundle ->
    val result = bundle.getString("bundleKey")
}
```

### 27. Fragment Result API如何使用？
**答案**：
```kotlin
// 发送结果
class FragmentA : Fragment() {
    fun sendResult() {
        setFragmentResult("requestKey", bundleOf("data" to "hello"))
    }
}

// 接收结果
class FragmentB : Fragment() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        parentFragmentManager.setFragmentResultListener(
            "requestKey", this
        ) { _, bundle ->
            val result = bundle.getString("data")
        }
    }
}
```

### 28. 什么是Fragment的嵌套（ChildFragmentManager）？
**答案**：
```kotlin
// Fragment内部嵌套Fragment
class ParentFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        // 使用childFragmentManager而非parentFragmentManager
        childFragmentManager.beginTransaction()
            .replace(R.id.child_container, ChildFragment())
            .commit()
    }
}
```
- 避免使用parent的FragmentManager导致事务冲突
- 嵌套Fragment的回退栈独立管理

### 29. ViewPager2与Fragment结合使用？
**答案**：
```kotlin
class ViewPagerAdapter(fragmentActivity: FragmentActivity) : 
    FragmentStateAdapter(fragmentActivity) {

    override fun getItemCount(): Int = 3

    override fun createFragment(position: Int): Fragment {
        return when (position) {
            0 -> FirstFragment()
            1 -> SecondFragment()
            2 -> ThirdFragment()
            else -> throw IllegalStateException()
        }
    }
}

// 使用
viewPager2.adapter = ViewPagerAdapter(this)
viewPager2.offscreenPageLimit = 1  // 预加载页数
```

### 30. Fragment的懒加载实现？
**答案**：
```kotlin
// ViewPager2方式
viewPager2.offscreenPageLimit = ViewPager2.OFFSCREEN_PAGE_LIMIT_DEFAULT

// 配合Lifecycle实现懒加载
class LazyFragment : Fragment() {

    private var isLoaded = false

    override fun onResume() {
        super.onResume()
        if (!isLoaded && !isHidden) {
            loadData()
            isLoaded = true
        }
    }

    // 或使用setMaxLifecycle（ViewPager2默认支持）
}
```

### 31. Fragment的onCreateView和onViewCreated区别？
**答案**：
| 方法 | 作用 | 使用场景 |
|------|------|----------|
| onCreateView | 创建并返回View | 初始化布局 |
| onViewCreated | View创建后回调 | 初始化视图（findViewById、设置监听器） |

```kotlin
override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
    return inflater.inflate(R.layout.fragment_my, container, false)
}

override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
    super.onViewCreated(view, savedInstanceState)
    // 初始化视图
    val textView = view.findViewById<TextView>(R.id.text_view)
    textView.text = "Hello"
}
```

### 32. Fragment的requireActivity()和getActivity()区别？
**答案**：
| 方法 | 返回值 | 风险 |
|------|--------|------|
| getActivity() | Activity? | 可能为null，需判空 |
| requireActivity() | Activity | 为空抛IllegalStateException |

```kotlin
// 推荐requireActivity()，但需确保在Attached状态使用
val activity = requireActivity()
```

### 33. DialogFragment相比普通Dialog的优势？
**答案**：
- 生命周期管理（旋转屏幕不丢失）
- 返回栈管理
- 与FragmentManager集成
- 支持全屏/浮动样式
- 可复用Fragment特性（ViewModel等）

```kotlin
class MyDialogFragment : DialogFragment() {
    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        return AlertDialog.Builder(requireContext())
            .setTitle("Title")
            .setMessage("Message")
            .setPositiveButton("OK") { _, _ -> }
            .create()
    }
}
```

### 34. BottomSheetDialogFragment的实现？
**答案**：
```kotlin
class MyBottomSheet : BottomSheetDialogFragment() {

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        return inflater.inflate(R.layout.bottom_sheet, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // 设置展开状态
        (dialog as? BottomSheetDialog)?.behavior?.apply {
            state = BottomSheetBehavior.STATE_EXPANDED
            peekHeight = 300.dpToPx()
            isHideable = true
        }
    }
}

// 显示
MyBottomSheet().show(parentFragmentManager, "tag")
```

### 35. Fragment的onSaveInstanceState保存哪些数据？
**答案**：
```kotlin
override fun onSaveInstanceState(outState: Bundle) {
    super.onSaveInstanceState(outState)
    // 手动保存数据
    outState.putString("edit_text", editText.text.toString())
    outState.putBoolean("checkbox_state", checkBox.isChecked)
}

override fun onViewStateRestored(savedInstanceState: Bundle?) {
    super.onViewStateRestored(savedInstanceState)
    savedInstanceState?.let {
        editText.setText(it.getString("edit_text"))
        checkBox.isChecked = it.getBoolean("checkbox_state")
    }
}
```
- 视图状态（EditText内容、ScrollView位置等）自动保存
- 手动保存业务数据到Bundle

---

## 三、Service（36-45题）

### 36. Service的两种启动方式？区别？
**答案**：
| 特性 | startService | bindService |
|------|-------------|-------------|
| 启动方式 | startService(intent) | bindService(intent, connection, flags) |
| 生命周期 | onCreate→onStartCommand→running→onDestroy | onCreate→onBind→running→onUnbind→onDestroy |
| 与调用者关系 | 无绑定，独立运行 | 绑定，组件解绑后可能销毁 |
| 通信方式 | 无法直接通信 | 通过IBinder接口通信 |
| 停止方式 | stopSelf()/stopService() | 所有客户端unbind后自动销毁 |
| 适用场景 | 长期后台任务 | 需要与组件交互的服务 |

### 37. Service的生命周期？
**答案**：
```
startService方式：
onCreate() → onStartCommand() → [运行中] → stopSelf()/stopService() → onDestroy()

bindService方式：
onCreate() → onBind() → [运行中] → 所有客户端unbind() → onUnbind() → onDestroy()

混合方式：
startService + bindService：需stopService且所有unbind后才销毁
```

### 38. IntentService是什么？（已废弃）
**答案**：
- 处理异步请求的Service
- 工作线程执行Intent
- 完成后自动停止
- **Android 30+已废弃，推荐使用WorkManager**

```kotlin
// 旧方式（已废弃）
class MyIntentService : IntentService("MyIntentService") {
    override fun onHandleIntent(intent: Intent?) {
        // 在后台线程执行
    }
}
```

### 39. 前台Service（Foreground Service）？
**答案**：
```kotlin
class MyForegroundService : Service() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = createNotification()
        startForeground(1, notification)  // 必须显示通知

        // 执行后台任务
        return START_NOT_STICKY
    }
}
```
- 必须显示通知（用户可见）
- 优先级高，不易被系统杀死
- Android 9+需要FOREGROUND_SERVICE权限
- Android 12+有启动限制（需特定场景）

### 40. Service和线程的区别？
**答案**：
| 特性 | Service | Thread |
|------|---------|--------|
| 运行线程 | 主线程（UI线程） | 独立线程 |
| 生命周期 | 有（系统管理） | 无（自行管理） |
| 优先级 | 较高 | 普通 |
| 跨进程 | 支持 | 不支持 |
| 使用场景 | 需要长期运行、跨组件 | 简单异步任务 |

**重要**：Service运行在主线程，耗时操作必须创建子线程！

### 41. AIDL是什么？使用场景？
**答案**：
- **Android Interface Definition Language**
- 跨进程通信接口定义语言
- Service与客户端在不同进程时使用

```aidl
// IRemoteService.aidl
interface IRemoteService {
    int getPid();
    void basicTypes(int anInt, long aLong, boolean aBoolean);
}
```

### 42. Messenger是什么？与AIDL区别？
**答案**：
| 特性 | Messenger | AIDL |
|------|-----------|------|
| 底层 | 基于AIDL | 直接AIDL |
| 实现复杂度 | 简单 | 复杂 |
| 线程安全 | 单线程（Handler） | 需自行处理多线程 |
| 适用场景 | 简单IPC，无需并发 | 复杂IPC，需要并发 |
| 数据类型 | 支持Bundle | 支持自定义类型 |

```kotlin
// Messenger服务端
val messenger = Messenger(object : Handler(Looper.getMainLooper()) {
    override fun handleMessage(msg: Message) {
        // 处理客户端消息
        val replyMessenger = msg.replyTo
        replyMessenger?.send(Message.obtain().apply { what = 1 })
    }
})

// 绑定返回messenger.binder
```

### 43. JobIntentService是什么？（已废弃）
**答案**：
- 兼容8.0后台限制的IntentService
- 8.0以下用普通Service，以上用JobScheduler
- **已废弃，推荐用WorkManager替代**

### 44. WorkManager与Service的区别？
**答案**：
| 特性 | WorkManager | Service |
|------|-------------|---------|
| 执行时机 | 延迟执行，条件满足时 | 立即执行 |
| 保证执行 | 是（即使应用关闭） | 否（可能被系统杀死） |
| Doze模式 | 兼容 | 前台Service兼容，后台不兼容 |
| 链式任务 | 支持 | 不支持 |
| 约束条件 | 支持（网络、电量等） | 不支持 |
| 适用场景 | 可延迟的后台任务 | 即时前台任务、长期运行 |

```kotlin
// WorkManager示例
val workRequest = OneTimeWorkRequestBuilder<MyWorker>()
    .setConstraints(
        Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
    )
    .build()

WorkManager.getInstance(context).enqueue(workRequest)
```

### 45. Android 8.0后台执行限制？
**答案**：
- 限制后台Service启动（startService抛IllegalStateException，需用startForegroundService）
- 限制隐式广播接收
- 推荐用JobScheduler/WorkManager替代后台Service

```kotlin
// Android 8+启动前台Service
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
    context.startForegroundService(intent)
} else {
    context.startService(intent)
}
```

---

## 四、BroadcastReceiver（46-55题）

### 46. BroadcastReceiver的注册方式？区别？
**答案**：
| 注册方式 | 位置 | 生命周期 | 适用场景 | Android 8+限制 |
|----------|------|----------|----------|----------------|
| 静态注册 | AndroidManifest | 应用未运行也可接收 | 系统广播（开机、网络变化） | 隐式广播受限 |
| 动态注册 | 代码中registerReceiver | 跟随组件生命周期 | 应用内广播、特定场景 | 无限制 |

```kotlin
// 动态注册
val receiver = MyReceiver()
val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
registerReceiver(receiver, filter)

// 注销
unregisterReceiver(receiver)  // 必须在onDestroy或对应生命周期中注销
```

### 47. 有序广播（Ordered Broadcast）和普通广播区别？
**答案**：
| 特性 | 普通广播 | 有序广播 |
|------|----------|----------|
| 传递方式 | 异步同时发送 | 按优先级顺序 |
| 接收顺序 | 同时接收 | 按priority顺序 |
| 拦截 | 不可拦截 | 可abortBroadcast() |
| 修改结果 | 不可 | 可setResultExtras() |
| 发送方式 | sendBroadcast() | sendOrderedBroadcast() |

```xml
<!-- 有序广播优先级 -->
<receiver android:priority="100">
    <intent-filter>
        <action android:name="com.example.ORDERED_ACTION" />
    </intent-filter>
</receiver>
```

### 48. LocalBroadcastManager是什么？（已废弃）
**答案**：
- 应用内广播，安全高效
- 已废弃，推荐用以下替代：
  - LiveData
  - Flow/StateFlow
  - EventBus

### 49. Android 8+对隐式广播的限制？
**答案**：
- targetSdk 26+，静态注册的隐式广播接收器大多数不再生效
- 系统广播（如BOOT_COMPLETED、TIMEZONE_CHANGED）仍可用
- 解决方案：
  - 动态注册
  - 显式Intent（setPackage/setComponent）
  - JobScheduler替代

### 50. BroadcastReceiver的onReceive运行在什么线程？
**答案**：
- **主线程（UI线程）**
- 耗时操作需转到Service或WorkManager
- 前台广播可用goAsync()

```kotlin
class MyReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pendingResult = goAsync()  // 前台广播，延长执行时间

        CoroutineScope(Dispatchers.IO).launch {
            // 执行耗时操作
            pendingResult.finish()
        }
    }
}
```

### 51. Sticky Broadcast是什么？（已废弃）
**答案**：
- 粘性广播，发送后一直保留
- 新注册接收器可立即收到
- **Android 5.0+已废弃，不安全**

### 52. 如何发送带权限的广播？
**答案**：
```kotlin
// 发送端
sendBroadcast(intent, Manifest.permission.RECEIVE_MY_BROADCAST)

// 接收端声明权限
<uses-permission android:name="com.example.RECEIVE_MY_BROADCAST" />

// 或自定义permission
<permission android:name="com.example.RECEIVE_MY_BROADCAST"
    android:protectionLevel="signature" />
```

### 53. BOOT_COMPLETED广播如何实现开机启动？
**答案**：
```xml
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />

<receiver android:name=".BootReceiver"
    android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.BOOT_COMPLETED" />
    </intent-filter>
</receiver>
```
- Android 3.1+需应用至少启动一次才生效
- Android 8+限制后台启动Activity

### 54. 广播接收器ANR原因？如何避免？
**答案**：
- **原因**：onReceive执行超过10秒
- **避免方法**：
  1. 使用goAsync()
  2. 启动Service处理
  3. 使用WorkManager
  4. 避免在onReceive中做耗时操作

### 55. 什么是显式广播和隐式广播？
**答案**：
| 特性 | 显式广播 | 隐式广播 |
|------|----------|----------|
| 目标 | 指定组件（setComponent/setPackage） | 只指定action |
| 匹配 | 直接启动目标 | 系统匹配所有声明的接收器 |
| Android 8+ | 无限制 | 静态注册受限 |
| 安全性 | 高 | 低（可能被恶意接收） |

---

## 五、ContentProvider（56-65题）

### 56. ContentProvider的作用？
**答案**：
- 跨应用数据共享的标准接口
- 封装数据并提供URI访问
- 底层可用SQLite、文件、网络等
- 统一CRUD接口

### 57. ContentProvider的URI格式？
**答案**：
```
content://authority/path/id

示例：
content://com.example.provider/users          // 所有用户
content://com.example.provider/users/1        // ID为1的用户
content://media/external/images/media         // 系统媒体图片
```

### 58. ContentResolver的作用？
**答案**：
```kotlin
// 客户端访问ContentProvider的接口
val resolver = contentResolver

// 查询
val cursor = resolver.query(
    Uri.parse("content://com.example.provider/users"),
    arrayOf("_id", "name", "age"),
    "age > ?",
    arrayOf("18"),
    "age DESC"
)

// 增删改
val uri = resolver.insert(userUri, contentValues)
resolver.update(userUri, contentValues, where, selectionArgs)
resolver.delete(userUri, where, selectionArgs)
```

### 59. Cursor是什么？如何正确使用？
**答案**：
```kotlin
val cursor = contentResolver.query(uri, null, null, null, null)
cursor?.use {
    while (it.moveToNext()) {
        val id = it.getLong(it.getColumnIndexOrThrow("_id"))
        val name = it.getString(it.getColumnIndexOrThrow("name"))
    }
}
// use{}自动关闭Cursor
```

### 60. ContentProvider的CRUD操作对应方法？
**答案**：
```kotlin
class MyProvider : ContentProvider() {
    override fun query(uri: Uri, projection: Array<String>?, selection: String?, selectionArgs: Array<String>?, sortOrder: String?): Cursor? {
        // 查询
    }

    override fun insert(uri: Uri, values: ContentValues?): Uri? {
        // 插入
    }

    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<String>?): Int {
        // 更新
    }

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<String>?): Int {
        // 删除
    }

    override fun getType(uri: Uri): String? {
        // 返回MIME类型
        return "vnd.android.cursor.dir/vnd.example.users"
    }
}
```

### 61. 什么是URI权限（URI Permission）？
**答案**：
```kotlin
// 临时授予其他应用对特定URI的读写权限
val intent = Intent(Intent.ACTION_VIEW).apply {
    setDataAndType(uri, "image/*")
    flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION
}
```
- 权限随接收组件生命周期结束而失效
- 用于安全共享文件

### 62. FileProvider是什么？
**答案**：
```xml
<!-- AndroidManifest.xml -->
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data
        android:name="android.support.FILE_PROVIDER_PATHS"
        android:resource="@xml/file_paths" />
</provider>
```
```xml
<!-- res/xml/file_paths.xml -->
<paths>
    <files-path name="internal" path="." />
    <external-files-path name="external" path="." />
    <cache-path name="cache" path="." />
</paths>
```
- 安全共享文件URI（content://替代file://）
- Android 7+强制使用

### 63. Room与ContentProvider的关系？
**答案**：
- Room是SQLite抽象层，不直接实现ContentProvider
- 可通过ContentProvider暴露Room数据库数据
- 或直接使用Room作为应用内数据库

### 64. ContentObserver的作用？
**答案**：
```kotlin
val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
    override fun onChange(selfChange: Boolean, uri: Uri?) {
        // 数据变化时回调
        refreshData()
    }
}

contentResolver.registerContentObserver(
    MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
    true,  // 监听子URI
    observer
)

// 注销
contentResolver.unregisterContentObserver(observer)
```

### 65. ContentProvider的android:exported属性？
**答案**：
- Android 12+，包含intent-filter的provider默认exported=true
- 应显式设置，避免数据泄露
- 非必要不exported，使用signature级别权限控制访问

---

## 六、Intent与IPC（66-75题）

### 66. Intent的显式和隐式区别？
**答案**：
| 特性 | 显式Intent | 隐式Intent |
|------|------------|------------|
| 目标指定 | setComponent/setClass | action/category/data |
| 匹配方式 | 直接启动 | 系统解析匹配 |
| 使用场景 | 应用内跳转 | 跨应用调用（分享、拍照） |
| 安全性 | 高 | 低（需处理多个匹配） |

```kotlin
// 显式
val intent = Intent(this, SecondActivity::class.java)

// 隐式
val intent = Intent(Intent.ACTION_VIEW).apply {
    data = Uri.parse("https://www.example.com")
}
```

### 67. Intent的data和type区别？
**答案**：
```kotlin
// data：URI
intent.data = Uri.parse("content://com.example.provider/users/1")

// type：MIME类型
intent.type = "image/*"

// 同时设置（注意：单独设置会清除另一个）
intent.setDataAndType(uri, "image/png")
```

### 68. PendingIntent是什么？使用场景？
**答案**：
```kotlin
// 延迟执行的Intent，由其他应用或系统触发
val intent = Intent(context, MyActivity::class.java)

val pendingIntent = PendingIntent.getActivity(
    context,
    0,
    intent,
    PendingIntent.FLAG_IMMUTABLE  // Android 12+强制要求
)

// 使用场景
// 1. 通知点击
notificationBuilder.setContentIntent(pendingIntent)

// 2. 小组件点击
appWidgetManager.updateAppWidget(appWidgetId, RemoteViews(context.packageName, R.layout.widget).apply {
    setOnClickPendingIntent(R.id.button, pendingIntent)
})

// 3. 闹钟
alarmManager.setExact(AlarmManager.RTC_WAKEUP, triggerTime, pendingIntent)
```

### 69. Parcelable和Serializable区别？
**答案**：
| 特性 | Parcelable | Serializable |
|------|------------|--------------|
| 来源 | Android专用 | Java标准 |
| 实现方式 | 手动实现 | 自动（标记接口） |
| 效率 | 高（二进制，内存优化） | 低（反射，IO开销） |
| 代码量 | 多（需实现方法） | 无（自动） |
| 推荐使用 | ✅ | ❌ |

```kotlin
// Parcelable（Kotlin插件自动生成）
@Parcelize
data class User(val name: String, val age: Int) : Parcelable
```

### 70. Bundle的容量限制？
**答案**：
- 底层Binder事务缓冲区约1MB（不同ROM有差异）
- Bundle过大（如传大图）会抛TransactionTooLargeException
- **避免传递大数据**：使用URI、文件路径、共享内存

### 71. Binder机制原理？
**答案**：
- Android IPC核心，基于C/S架构
- 客户端通过BinderProxy调用服务端Stub
- 底层mmap实现一次数据拷贝
- 效率高于传统IPC（管道、Socket等两次拷贝）

### 72. AIDL生成的文件结构？
**答案**：
```
IXxx.aidl → IXxx.java
  ├── Stub（服务端实现，继承Binder）
  │   └── asInterface()
  └── Proxy（客户端代理）
      └── 调用远程方法
```

### 73. Messenger底层是AIDL吗？
**答案**：
- **是**，Messenger基于AIDL实现（IMessenger.aidl）
- 封装了IBinder和Handler
- 简化跨进程通信，但仅支持单线程处理

### 74. 什么是IBinder？
**答案**：
- 远程对象基接口
- 实现跨进程调用的核心
- Binder类实现IBinder
- AIDL和Messenger的基础

### 75. 跨进程传递大数据方案？
**答案**：
1. **ContentProvider**：URI方式共享
2. **FileProvider**：文件共享
3. **Socket**：网络传输
4. **共享内存（Ashmem）**：Ashmem或MemoryFile
5. **避免直接传递**：Binder限制1MB

---

## 七、权限与安全（76-85题）

### 76. Android权限分类？
**答案**：
| 类型 | 特点 | 示例 |
|------|------|------|
| 普通权限 | 安装时自动授予 | INTERNET, ACCESS_NETWORK_STATE |
| 危险权限 | 运行时需申请 | CAMERA, LOCATION, READ_CONTACTS |
| 特殊权限 | 需特殊申请流程 | SYSTEM_ALERT_WINDOW, WRITE_SETTINGS |
| 签名权限 | 同签名应用可用 | 自定义权限 |

### 77. 运行时权限申请流程？
**答案**：
```kotlin
// 1. 检查权限
when {
    ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) 
        == PackageManager.PERMISSION_GRANTED -> {
        // 已授权
    }
    shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) -> {
        // 2. 显示解释UI
        showRationaleDialog()
    }
    else -> {
        // 3. 申请权限
        requestPermissionLauncher.launch(Manifest.permission.CAMERA)
    }
}

// 4. 处理结果
val requestPermissionLauncher = registerForActivityResult(
    ActivityResultContracts.RequestPermission()
) { isGranted ->
    if (isGranted) {
        // 授权成功
    } else {
        // 授权失败
    }
}
```

### 78. shouldShowRequestPermissionRationale作用？
**答案**：
- 判断是否应该显示权限申请理由
- `true`：用户之前拒绝但未勾选"不再询问"
- `false`：首次申请或已勾选"不再询问"

### 79. Android 11+的权限变化？
**答案**：
- 一次性权限（仅本次允许）
- 后台位置权限需分步申请
- 自动重置未使用应用权限
- 包可见性限制（queries声明）

```xml
<queries>
    <package android:name="com.example.app" />
    <intent>
        <action android:name="android.intent.action.SEND" />
        <data android:mimeType="image/plain" />
    </intent>
</queries>
```

### 80. Android 13+的通知权限？
**答案**：
- 新增`POST_NOTIFICATIONS`运行时权限
- 需动态申请
- 用户可在系统设置中关闭通知

```kotlin
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
    requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
}
```

### 81. 什么是签名级权限（signature permission）？
**答案**：
- 只有与声明权限应用相同签名的应用才能获得
- 用于同开发者应用间安全共享

```xml
<permission android:name="com.example.PRIVATE_PERMISSION"
    android:protectionLevel="signature" />
```

### 82. Android Keystore系统？
**答案**：
- 硬件-backed密钥存储
- 密钥不导出到应用进程
- 用于加密、签名、生物识别等安全操作

```kotlin
val keyGenerator = KeyGenerator.getInstance("AES", "AndroidKeyStore")
val keyGenParameterSpec = KeyGenParameterSpec.Builder("my_key",
    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
    .setUserAuthenticationRequired(true)  // 需要生物识别
    .build()
keyGenerator.init(keyGenParameterSpec)
keyGenerator.generateKey()
```

### 83. NetworkSecurityConfig作用？
**答案**：
```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">localhost</domain>
    </domain-config>
    <pin-set expiration="2024-01-01">
        <pin digest="SHA-256">sha256/AAAAAAAAAAAAAAAAAAAAAAA=</pin>
    </pin-set>
</network-security-config>
```
- 自定义CA证书
- 明文流量许可
- 证书固定（pinning）

### 84. 什么是ProGuard/R8混淆？
**答案**：
- 代码压缩、优化、混淆工具
- 删除无用代码
- 重命名类/方法/字段
- 增加反编译难度
- 减小包体积

```proguard
# 保留类名
-keep class com.example.model.** { *; }

# 保留注解
-keepattributes *Annotation*
```

### 85. Android 12+的exported属性强制要求？
**答案**：
- 包含intent-filter的Activity/Service/Receiver/Provider必须显式声明exported属性
- 否则编译报错
- 安全建议：非必要不exported

```xml
<activity android:name=".MainActivity"
    android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
    </intent-filter>
</activity>
```

---

## 八、存储与数据（86-95题）

### 86. Android存储分类？
**答案**：
| 类型 | 路径 | 特点 | 访问方式 |
|------|------|------|----------|
| 内部存储 | /data/data/包名 | 私有，应用卸载删除 | 直接访问 |
| 外部私有 | /sdcard/Android/data/包名 | 私有，应用卸载删除 | 直接访问 |
| 外部共享 | /sdcard/Pictures等 | 共享，应用卸载保留 | MediaStore/SAF |
| 系统分区 | /system | 只读 | 需root |

### 87. SharedPreferences的apply和commit区别？
**答案**：
| 方法 | 提交方式 | 返回值 | 线程安全 | 推荐使用 |
|------|----------|--------|----------|----------|
| apply() | 异步 | 无 | 是 | ✅ |
| commit() | 同步 | boolean | 是 | ❌（主线程阻塞） |

```kotlin
val prefs = getSharedPreferences("settings", Context.MODE_PRIVATE)
prefs.edit {
    putString("name", "Tom")
    putInt("age", 25)
    apply()  // 异步提交
}
```

### 88. SharedPreferences的MODE_MULTI_PROCESS？（已废弃）
**答案**：
- 允许多进程访问，但不可靠
- 已废弃
- 推荐替代：ContentProvider、MMKV、DataStore

### 89. DataStore是什么？替代SharedPreferences？
**答案**：
```kotlin
// Preferences DataStore
val Context.dataStore by preferencesDataStore(name = "settings")

val NAME = stringPreferencesKey("name")
val AGE = intPreferencesKey("age")

// 写入
lifecycleScope.launch {
    context.dataStore.edit { settings ->
        settings[NAME] = "Tom"
        settings[AGE] = 25
    }
}

// 读取
val nameFlow: Flow<String> = context.dataStore.data
    .map { preferences -> preferences[NAME] ?: "" }
```
- 异步API，非阻塞
- 事务性，类型安全
- 解决SP的ANR问题

### 90. SQLiteOpenHelper的作用？
**答案**：
```kotlin
class MyDatabaseHelper(context: Context) : SQLiteOpenHelper(
    context, "mydb", null, 2  // 版本2
) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE users (_id INTEGER PRIMARY KEY, name TEXT)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE users ADD COLUMN age INTEGER")
        }
    }
}
```
- 管理数据库创建和版本升级
- onCreate：首次创建
- onUpgrade：版本迁移

### 91. Room的三层架构？
**答案**：
```kotlin
// 1. Entity - 数据实体
@Entity(tableName = "users")
data class User(
    @PrimaryKey val id: Int,
    @ColumnInfo(name = "name") val name: String
)

// 2. DAO - 数据访问对象
@Dao
interface UserDao {
    @Query("SELECT * FROM users")
    fun getAll(): List<User>

    @Insert
    fun insert(user: User)
}

// 3. Database - 数据库持有者
@Database(entities = [User::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun userDao(): UserDao
}
```

### 92. Room的迁移（Migration）？
**答案**：
```kotlin
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(database: SupportSQLiteDatabase) {
        database.execSQL("ALTER TABLE users ADD COLUMN age INTEGER")
    }
}

val db = Room.databaseBuilder(context, AppDatabase::class.java, "mydb")
    .addMigrations(MIGRATION_1_2)
    .build()

// 破坏性重建（数据丢失）
.fallbackToDestructiveMigration()
```

### 93. MMKV是什么？优势？
**答案**：
- 腾讯开源的高性能键值存储
- 基于mmap，读写速度远超SharedPreferences
- 支持多进程

```kotlin
// 初始化
MMKV.initialize(context)

// 使用
val mmkv = MMKV.defaultMMKV()
mmkv.encode("name", "Tom")
val name = mmkv.decodeString("name")
```

### 94. Android 10+分区存储（Scoped Storage）？
**答案**：
- 应用只能访问自己的私有目录和特定共享目录
- 需申请READ_EXTERNAL_STORAGE/WRITE_EXTERNAL_STORAGE
- 或使用Storage Access Framework（SAF）
- 或使用MediaStore

```kotlin
// 访问共享媒体
val projection = arrayOf(MediaStore.Images.Media._ID, MediaStore.Images.Media.DISPLAY_NAME)
val cursor = contentResolver.query(
    MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
    projection, null, null, null
)
```

### 95. MediaStore API作用？
**答案**：
- 访问共享媒体文件（图片、视频、音频）的标准API
- 无需存储权限即可读取自己创建的文件
- 支持查询、插入、更新、删除

---

## 九、多线程与异步（96-100题）

### 96. Android主线程（UI线程）限制？
**答案**：
- 禁止在主线程执行网络请求、大量IO、复杂计算
- 会导致ANR（Application Not Responding）
- 耗时操作需在子线程执行

```kotlin
// 错误！主线程网络请求
val response = httpClient.get("https://api.example.com")  // NetworkOnMainThreadException

// 正确
lifecycleScope.launch(Dispatchers.IO) {
    val response = httpClient.get("https://api.example.com")
    withContext(Dispatchers.Main) {
        textView.text = response
    }
}
```

### 97. AsyncTask是什么？（已废弃）
**答案**：
- 封装了线程池和Handler的异步任务类
- 已废弃（Android 11）
- 推荐用Kotlin协程或Executor替代

```kotlin
// 旧方式（已废弃）
class MyTask : AsyncTask<Void, Void, String>() {
    override fun doInBackground(vararg params: Void?): String {
        return fetchData()
    }
    override fun onPostExecute(result: String?) {
        textView.text = result
    }
}
```

### 98. Handler、Looper、MessageQueue关系？
**答案**：
```
Looper（循环器）
  └── 管理MessageQueue（消息队列）
       └── 存储Message（消息）
            └── Handler（处理器）发送和处理
```
- 一个线程只有一个Looper
- 主线程默认有Looper（Looper.getMainLooper()）
- 子线程需手动调用Looper.prepare()和Looper.loop()

```kotlin
// 子线程创建Handler
val thread = Thread {
    Looper.prepare()
    val handler = Handler(Looper.myLooper()!!) {
        // 处理消息
        true
    }
    Looper.loop()
}
thread.start()
```

### 99. HandlerThread是什么？
**答案**：
- 自带Looper的工作线程
- 用于需要Handler机制的后台线程
- IntentService底层实现

```kotlin
val handlerThread = HandlerThread("MyHandlerThread")
handlerThread.start()

val handler = Handler(handlerThread.looper) {
    // 在后台线程处理消息
    true
}

// 使用完需quit
handlerThread.quitSafely()
```

### 100. Kotlin协程在Android中的优势？
**答案**：
1. **轻量级线程**：挂起非阻塞，一个线程可运行多个协程
2. **结构化并发**：自动取消子协程，避免内存泄漏
3. **Lifecycle集成**：lifecycleScope/viewModelScope自动管理生命周期
4. **简化异步代码**：顺序写异步逻辑，避免回调地狱

```kotlin
// 生命周期感知
lifecycleScope.launch {
    val data = withContext(Dispatchers.IO) {
        repository.fetchData()
    }
    textView.text = data
}

// ViewModelScope（配置变更保留）
viewModelScope.launch {
    flow.collect { value ->
        _uiState.value = value
    }
}
```

---

> **总结**：Android四大组件（Activity、Service、BroadcastReceiver、ContentProvider）是应用开发的基石，理解生命周期、IPC机制、权限模型和存储方案是成为Android开发者的核心。建议结合官方文档和实际项目经验来巩固这些知识。
